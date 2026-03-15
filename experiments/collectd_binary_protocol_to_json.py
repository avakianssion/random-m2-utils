#! /usr/bin/env python3
"""
-*- coding: utf-8 -*-
Collectd network protocol parser (Python 3 version)

# NOTE:
This work, for the most part was done here https://github.com/sayar/python-collectd-parser and most of the credit goes to them.
In this version, I had to make some updates to make python3 happy.
It's also eaier for me to house this in my own repo.
"""

import socket
import struct
from datetime import datetime
from copy import deepcopy
import json
#############################################################################

DEFAULT_PORT = 25826
DEFAULT_IPv4_GROUP = "239.192.74.66"
DEFAULT_IPv6_GROUP = "ff18::efc0:4a42"

_BUFFER_SIZE = 65535  # safe > 65531

#############################################################################

class CollectdException(Exception):
    pass

class CollectdValueError(CollectdException, ValueError):
    pass

class CollectdDecodeError(CollectdValueError):
    pass

class CollectdUnsupportedDSType(CollectdValueError):
    pass

class CollectdUnsupportedMessageType(CollectdValueError):
    pass

class CollectdBufferOverflow(CollectdValueError):
    pass

#############################################################################

# Message kinds
TYPE_HOST            = 0x0000
TYPE_TIME            = 0x0001
TYPE_PLUGIN          = 0x0002
TYPE_PLUGIN_INSTANCE = 0x0003
TYPE_TYPE            = 0x0004
TYPE_TYPE_INSTANCE   = 0x0005
TYPE_VALUES          = 0x0006
TYPE_INTERVAL        = 0x0007
TYPE_TIMEHR          = 0x0008
TYPE_INTERVALHR      = 0x0009

# Notifications
TYPE_MESSAGE         = 0x0100
TYPE_SEVERITY        = 0x0101

TYPE_SIGN_SHA256     = 0x0200
TYPE_ENCR_AES256     = 0x0210

# DS kinds
DS_TYPE_COUNTER      = 0
DS_TYPE_GAUGE        = 1
DS_TYPE_DERIVE       = 2
DS_TYPE_ABSOLUTE     = 3

header = struct.Struct("!2H")
number = struct.Struct("!Q")
signed_number = struct.Struct("!q") # DERIVE are signed long longs
short  = struct.Struct("!H")
double = struct.Struct("<d")

assert double.size == number.size == signed_number.size == 8

#############################################################################

_values_header_size = header.size + short.size
_single_value_size = 1 + 8  # type byte + value

_ds_type_decoder = {
    DS_TYPE_COUNTER:    number,
    DS_TYPE_ABSOLUTE:   number,
    DS_TYPE_DERIVE:     signed_number,
    DS_TYPE_GAUGE:      double
}

def decode_network_values(ptype, plen, buf):
    assert ptype == TYPE_VALUES

    nvalues = short.unpack_from(buf, header.size)[0]
    values_tot_size = _values_header_size + nvalues * _single_value_size
    if values_tot_size != plen:
        raise CollectdValueError(
            f"Values total size != Part len ({values_tot_size} vs {plen})"
        )

    results = []
    off = _values_header_size + nvalues

    for dstype in buf[_values_header_size:off]:
        try:
            decoder = _ds_type_decoder[dstype]
        except KeyError:
            raise CollectdUnsupportedDSType(f"DS type {dstype} unsupported")
        results.append((dstype, decoder.unpack_from(buf, off)[0]))
        off += 8
    return results

def decode_network_number(ptype, plen, buf):
    return number.unpack_from(buf, header.size)[0]

def decode_network_string(ptype, plen, buf):
    data = buf[header.size:plen-1]
    return data.decode("utf-8", errors="ignore")

_decoders = {
    TYPE_VALUES         : decode_network_values,
    TYPE_TIME           : decode_network_number,
    TYPE_INTERVAL       : decode_network_number,
    TYPE_HOST           : decode_network_string,
    TYPE_PLUGIN         : decode_network_string,
    TYPE_PLUGIN_INSTANCE: decode_network_string,
    TYPE_TYPE           : decode_network_string,
    TYPE_TYPE_INSTANCE  : decode_network_string,
    TYPE_MESSAGE        : decode_network_string,
    TYPE_SEVERITY       : decode_network_number,
    TYPE_TIMEHR         : decode_network_number,
    TYPE_INTERVALHR     : decode_network_number,
}

def decode_network_packet(buf):
    off = 0
    blen = len(buf)

    while off < blen:
        try:
            ptype, plen = header.unpack_from(buf, off)
        except struct.error as err:
            raise CollectdDecodeError(err)

        if not plen:
            raise CollectdValueError(f"Invalid part with size=0: buflen={blen} off={off} ptype={ptype}")

        rest = blen - off
        if plen > rest:
            raise CollectdBufferOverflow(
                f"Encoded part size greater than remaining data: buflen={blen} off={off} vsize={plen}"
            )

        try:
            decoder = _decoders[ptype]
        except KeyError:
            raise CollectdUnsupportedMessageType(f"Part type {ptype} not recognized (off={off})")

        try:
            res = decoder(ptype, plen, buf[off:])
        except struct.error as err:
            raise CollectdDecodeError(err)

        yield ptype, res
        off += plen

#############################################################################

def cdtime_to_time(cdt):
    sec = cdt >> 30
    nsec = ((cdt & 0b111111111111111111111111111111) / 1.073741824) / 10**9
    assert 0 <= nsec < 1
    return sec + nsec

class Data(object):
    time = None
    interval = None
    host = None
    plugin = None
    plugininstance = None
    type = None
    typeinstance = None

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    @property
    def datetime(self):
        return datetime.fromtimestamp(self.time) if self.time else None

    @property
    def source(self):
        res = []
        if self.host:
            res.append(self.host)
        for attr in ('plugin', 'plugininstance', 'type', 'typeinstance'):
            val = getattr(self, attr)
            if val:
                res.append("/")
                res.append(val)
        return ''.join(res)

    def __str__(self):
        return f"[{self.time}] {self.source}"

class Notification(Data):
    FAILURE  = 1
    WARNING  = 2
    OKAY     = 4

    SEVERITY = {
        FAILURE: "FAILURE",
        WARNING: "WARNING",
        OKAY   : "OKAY",
    }

    __severity = 0
    message  = ""

    @property
    def severity(self):
        return self.__severity

    @severity.setter
    def severity(self, value):
        if value in (self.FAILURE, self.WARNING, self.OKAY):
            self.__severity = value

    @property
    def severitystring(self):
        return self.SEVERITY.get(self.severity, "UNKNOWN")

    def __str__(self):
        return f"{super().__str__()} [{self.severitystring}] {self.message}"

class Values(Data, list):
    def __str__(self):
        return f"{Data.__str__(self)} {list.__str__(self)}"

#############################################################################

class Parser(object):
    Values = Values
    Notification = Notification

    def receive(self):
        raise NotImplementedError

    def decode(self, buf=None):
        if buf is None:
            buf, _ = self.receive()
        return decode_network_packet(buf)

    def interpret_opcodes(self, iterable):
        vl = self.Values()
        nt = self.Notification()

        for kind, data in iterable:
            if kind == TYPE_TIME:
                vl.time = nt.time = data
            elif kind == TYPE_TIMEHR:
                vl.time = nt.time = cdtime_to_time(data)
            elif kind == TYPE_INTERVAL:
                vl.interval = data
            elif kind == TYPE_INTERVALHR:
                vl.interval = cdtime_to_time(data)
            elif kind == TYPE_HOST:
                vl.host = nt.host = data
            elif kind == TYPE_PLUGIN:
                vl.plugin = nt.plugin = data
            elif kind == TYPE_PLUGIN_INSTANCE:
                vl.plugininstance = nt.plugininstance = data
            elif kind == TYPE_TYPE:
                vl.type = nt.type = data
            elif kind == TYPE_TYPE_INSTANCE:
                vl.typeinstance = nt.typeinstance = data
            elif kind == TYPE_SEVERITY:
                nt.severity = data
            elif kind == TYPE_MESSAGE:
                nt.message = data
                yield deepcopy(nt)
            elif kind == TYPE_VALUES:
                vl[:] = data
                yield deepcopy(vl)

    def interpret(self, input=None):
        if isinstance(input, (type(None), str, bytes)):
            input = self.decode(input)
        return self.interpret_opcodes(input)

class Reader(Parser):
    def __init__(self, host=None, port=DEFAULT_PORT, multicast=False):
        if host is None:
            multicast = True
            host = DEFAULT_IPv4_GROUP

        self.host, self.port = host, port
        self.ipv6 = ":" in self.host

        family, socktype, proto, _, sockaddr = socket.getaddrinfo(
            None if multicast else self.host, self.port,
            socket.AF_INET6 if self.ipv6 else socket.AF_UNSPEC,
            socket.SOCK_DGRAM, 0, socket.AI_PASSIVE
        )[0]

        self._sock = socket.socket(family, socktype, proto)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(sockaddr)

        if multicast:
            if hasattr(socket, "SO_REUSEPORT"):
                self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

            if family == socket.AF_INET:
                val = struct.pack("4sl", socket.inet_aton(self.host), socket.INADDR_ANY)
            elif family == socket.AF_INET6:
                raise NotImplementedError("IPv6 multicast not implemented")
            else:
                raise ValueError("Unsupported address family")

            self._sock.setsockopt(
                socket.IPPROTO_IP if not self.ipv6 else socket.IPPROTO_IPV6,
                socket.IP_ADD_MEMBERSHIP, val
            )
            self._sock.setsockopt(
                socket.IPPROTO_IP if not self.ipv6 else socket.IPPROTO_IPV6,
                socket.IP_MULTICAST_LOOP, 0
            )

    def receive(self):
        return self._sock.recvfrom(_BUFFER_SIZE)

    def close(self):
        self._sock.close()

