use anyhow::Result;
use axum::{
    extract::State,
    http::StatusCode,
    response::IntoResponse,
    routing::post,
    Router,
};
use clap::Parser;
use serde::{Deserialize, Serialize};
use std::{sync::Arc, time::Duration};
use tokio::{    
    fs::OpenOptions,
    io::AsyncWriteExt,
    net::UdpSocket,
    sync::mpsc::{self, UnboundedReceiver, UnboundedSender},
    time::{interval, Instant},
};
use tracing::{debug, info, warn};

// Flags over configs!
#[derive(Parser, Debug, Clone)]
#[command(author, version, about = "Collectd HTTP Receiver - A high-performance metrics collector")]
pub struct Config {
    /// Host to bind to
    #[arg(long, default_value = "0.0.0.0")]
    pub host: String,

    /// Port to listen on
    #[arg(short, long, default_value = "8080")]
    pub port: u16,

    /// Batch size before sending/writing
    #[arg(short, long, default_value = "100")]
    pub batch_size: usize,

    /// Output mode: "disk" or "udp"
    #[arg(short, long, default_value = "disk")]
    pub output_mode: String,

    /// Output file path (for disk mode)
    #[arg(long, default_value = "collectd.out")]
    pub output_file: String,

    /// UDP target host (for UDP mode)
    #[arg(long, default_value = "localhost")]
    pub udp_host: String,

    /// UDP target port (for UDP mode)
    #[arg(long, default_value = "9999")]
    pub udp_port: u16,

    /// Flush interval in milliseconds
    #[arg(long, default_value = "1000")]
    pub flush_interval_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CollectdMetric {
    pub time: Option<f64>,
    pub host: Option<String>,
    pub plugin: Option<String>,
    pub plugin_instance: Option<String>,
    #[serde(rename = "type")]
    pub type_: Option<String>,
    pub type_instance: Option<String>,
    pub value: Option<serde_json::Value>,
    pub values: Option<Vec<serde_json::Value>>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ProcessedMetric {
    pub time: Option<f64>,
    pub host: Option<String>,
    pub plugin: Option<String>,
    pub plugin_instance: Option<String>,
    pub type_: Option<String>,
    pub type_instance: Option<String>,
    pub value: serde_json::Value,
}

#[derive(Clone)]
pub struct AppState {
    pub sender: UnboundedSender<ProcessedMetric>,
    pub config: Arc<Config>,
}

// HTTP handler for collectd metrics
async fn collectd_handler(
    State(state): State<AppState>,
    body: String,
) -> Result<impl IntoResponse, StatusCode> {
    let raw_metrics: Vec<CollectdMetric> = match serde_json::from_str(&body) {
        Ok(single_metric) => vec![single_metric],
        Err(_) => {
            // Try parsing as array
            match serde_json::from_str(&body) {
                Ok(metrics) => metrics,
                Err(e) => {
                    warn!("Failed to parse JSON: {}", e);
                    return Err(StatusCode::BAD_REQUEST);
                }
            }
        }
    };

    debug!("Received {} metrics", raw_metrics.len());

    // Process each metric
    let mut processed_count = 0;
    for raw_metric in raw_metrics {
        let processed_metrics = process_metric(raw_metric);
        for metric in processed_metrics {
            if let Err(_) = state.sender.send(metric) {
                warn!("Failed to send metric to processing queue");
                return Err(StatusCode::INTERNAL_SERVER_ERROR);
            }
            processed_count += 1;
        }
    }

    debug!("Processed {} metrics", processed_count);
    Ok("OK\n")
}

fn process_metric(metric: CollectdMetric) -> Vec<ProcessedMetric> {
    let mut processed = Vec::new();

    // Handle both 'values' and 'value' fields
    let values = if let Some(values_array) = metric.values {
        values_array
    } else if let Some(single_value) = metric.value {
        vec![single_value]
    } else {
        return processed;
    };

    // Create a processed metric for each value that is a flat, eye candy object
    for value in values {
        let processed_metric = ProcessedMetric {
            time: metric.time,
            host: metric.host.clone(),
            plugin: metric.plugin.clone(),
            plugin_instance: metric.plugin_instance.clone(),
            type_: metric.type_.clone(),
            type_instance: metric.type_instance.clone(),
            value,
        };
        processed.push(processed_metric);
    }

    processed
}

// Disk writer worker
// I wanna use this for testing and not having to bring over my dirty little listener
async fn disk_writer(mut receiver: UnboundedReceiver<ProcessedMetric>, config: Config) -> Result<()> {
    info!("Starting disk writer, output: {}", config.output_file);
    
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&config.output_file)
        .await?;

    let mut buffer = Vec::with_capacity(config.batch_size);
    let mut flush_timer = interval(Duration::from_millis(config.flush_interval_ms));
    let mut last_write = Instant::now();

    loop {
        tokio::select! {
            // Receive new metrics
            metric_opt = receiver.recv() => {
                match metric_opt {
                    Some(metric) => {
                        buffer.push(metric);
                        
                        // Write if buffer is full
                        if buffer.len() >= config.batch_size {
                            write_batch_to_disk(&mut file, &mut buffer).await?;
                            last_write = Instant::now();
                        }
                    }
                    None => {
                        // Channel closed, flush and exit
                        if !buffer.is_empty() {
                            write_batch_to_disk(&mut file, &mut buffer).await?;
                        }
                        info!("Disk writer shutting down");
                        break;
                    }
                }
            }
            
            // Periodic flush
            _ = flush_timer.tick() => {
                if !buffer.is_empty() && last_write.elapsed() > Duration::from_millis(config.flush_interval_ms) {
                    write_batch_to_disk(&mut file, &mut buffer).await?;
                    last_write = Instant::now();
                }
            }
        }
    }

    Ok(())
}

async fn write_batch_to_disk(file: &mut tokio::fs::File, buffer: &mut Vec<ProcessedMetric>) -> Result<()> {
    for metric in buffer.drain(..) {
        let json_line = serde_json::to_vec(&metric)?;
        file.write_all(&json_line).await?;
        file.write_all(b"\n").await?;
    }
    file.flush().await?;
    debug!("Wrote batch to disk");
    Ok(())
}

// UDP sender worker
async fn udp_sender(mut receiver: UnboundedReceiver<ProcessedMetric>, config: Config) -> Result<()> {
    let target_addr = format!("{}:{}", config.udp_host, config.udp_port);
    info!("Starting UDP sender, target: {}", target_addr);
    
    let socket = UdpSocket::bind("0.0.0.0:0").await?;
    socket.connect(&target_addr).await?;

    let mut buffer = Vec::with_capacity(config.batch_size);
    let mut flush_timer = interval(Duration::from_millis(config.flush_interval_ms));
    let mut last_send = Instant::now();

    loop {
        tokio::select! {
            // Receive new metrics
            metric_opt = receiver.recv() => {
                match metric_opt {
                    Some(metric) => {
                        buffer.push(metric);
                        
                        // Send if buffer is full
                        if buffer.len() >= config.batch_size {
                            send_batch_udp(&socket, &mut buffer).await?;
                            last_send = Instant::now();
                        }
                    }
                    None => {
                        // Channel closed, flush and exit
                        if !buffer.is_empty() {
                            send_batch_udp(&socket, &mut buffer).await?;
                        }
                        info!("UDP sender shutting down");
                        break;
                    }
                }
            }
            
            // Periodic flush
            _ = flush_timer.tick() => {
                if !buffer.is_empty() && last_send.elapsed() > Duration::from_millis(config.flush_interval_ms) {
                    send_batch_udp(&socket, &mut buffer).await?;
                    last_send = Instant::now();
                }
            }
        }
    }

    Ok(())
}

async fn send_batch_udp(socket: &UdpSocket, buffer: &mut Vec<ProcessedMetric>) -> Result<()> {
    let batch_json = serde_json::to_vec(buffer)?;
    socket.send(&batch_json).await?;
    debug!("Sent batch of {} metrics via UDP", buffer.len());
    buffer.clear();
    Ok(())
}

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing
    tracing_subscriber::fmt()
        .with_env_filter("info")
        .init();

    // Parse command line arguments
    let config = Config::parse();
    info!("Starting collectd HTTP receiver with config: {:?}", config);

    // Create channel for metrics
    let (tx, rx) = mpsc::unbounded_channel::<ProcessedMetric>();

    // Start the appropriate worker based on config
    match config.output_mode.as_str() {
        "disk" => {
            let config_clone = config.clone();
            tokio::spawn(async move {
                if let Err(e) = disk_writer(rx, config_clone).await {
                    warn!("Disk writer error: {}", e);
                }
            });
        }
        "udp" => {
            let config_clone = config.clone();
            tokio::spawn(async move {
                if let Err(e) = udp_sender(rx, config_clone).await {
                    warn!("UDP sender error: {}", e);
                }
            });
        }
        _ => {
            return Err(anyhow::anyhow!("Invalid output mode: {}", config.output_mode));
        }
    }

    // Create app state
    let state = AppState {
        sender: tx,
        config: Arc::new(config.clone()),
    };

    // Build the router
    let app = Router::new()
        .route("/", post(collectd_handler))
        .route("/collectd", post(collectd_handler))
        .with_state(state);

    // Start the server
    let listener = tokio::net::TcpListener::bind(format!("{}:{}", config.host, config.port)).await?;
    info!("Listening on http://{}:{}", config.host, config.port);

    axum::serve(listener, app).await?;

    Ok(())
}