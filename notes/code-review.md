# Nugget of Wisdom on Code Review from Allen Holub 

"My experience is that PR-driven reviews rarely find real bugs. They don't improve quality in ways that matter. They DO create bottlenecks, dependencies, and context-swap overhead, however, and all that pushes out delivery time and increases the cost of development with no balancing benefit.

I will grant that two or more sets of eyes on the code leads to better code, but in my experience, the best time to do that is when the code is being written, not after the fact. Work in a pair, or better yet, a mob/ensemble.

One of the teams at Hunter Industries, which mob/ensemble programs 100% of the time on 100% of the code, went a year and a half with no bugs reported against their code, with zero productivity hit. (Quite the contrary—they work very fast.) Bugs are so rare across all the teams, in fact, that they don't bother to track them. When a bug comes up, they fix it. Right then and there.

If you're working in a regulatory environment, the Driver signs the code, and then any other member of the mob/ensemble can sign off on the review, all as part of the commit/push process, so that's a non-issue. There's also a myth that it's best if the reviewer is not familiar with the code. I *really* don't buy that. An isolated reviewer doesn't understand the context. They don't know why design decisions were made. They have to waste a vast amount of time coming up to speed. They are also often not in a position to know whether the code will actually work. Consequently, they usually focus on trivia like formatting. That benefits nobody."
