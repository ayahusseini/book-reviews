---
title: TIL 2026-04-09  - Multi-Threading and Race Conditions
author: Aya
type: til
slug: TIL-2026-04-09-Race-Conditions
date: 2026-04-09
---

# Contents

# Technical

- [[#Multi-Threading in computers|Multi-Threading in computers]]
	- [[#Running more programs than we have cores|Running more programs than we have cores]]
	- [[#Concurrency vs Parallelism|Concurrency vs Parallelism]]
	- [[#Threads|Threads]]
	- [[#More on the `top` command|More on the `top` command]]


# Multi-Threading in computers

In a previous [[TIL-2026-03-26#Running multiple programs in parallel in bash|TIL post]], I talked about running parallel bash commands at a fairly shallow level. The inner workings of the computer were black-boxed: we have a shell that can be used to speak to "workers" on a computer, and we can get a finite number of these workers to get through a queue of tasks together.

Before getting into this topic again, I'll go over what these workers actually are at the level underneath the shell. Each "worker" is a CPU core.

Take a kitchen:

- The **kitchen counter** is the RAM - it has the ingredients (data) laid out and ready to be used.
- The **recipe book** is the program.
- The chef is the CPU. The chef's job is to fetch the next queued instruction (read the recipe book), decode it, and execute it.

The CPU often gets called the "brain" of the computer, but that's over-anthropomorphising it. It is stupid but powerful, executing the fetch-decode-execute cycle many, many times over. How do we make a CPU even more powerful?

- Improve the raw clock speed (number of execution cycles per second)
- Add more chefs. Physically, this means adding more **cores** to your computer. Having four cores means that 4 tasks can be handled in parallel
- Cache results. This is like adding a shelf next to the chef containing ingredients they're **likely** to need next.

Back to bash now. When we run a program, a core is assigned to that process. This assignment isn't permanent. The underlying operating system (OS) has a **scheduler** which switches cores between different processes incredibly fast. 

## Running more programs than we have cores

A typical computer has a handful of cores, usually between 4 and 16. A natural question arises: I'm almost certainly running more than 16 programs on my computer right now. If parallel processes are handled by parallel cores, how is that possible? The answer is an **illusion of parallelism**, created by **time-slicing**.

True parallelism is when we have four chefs working on four different recipe steps simultaneously. Note, nothing is stopping a single chef from multitasking on his own. A chef can work on 10 different dishes at once; they just can't literally execute two steps at the same instant. This means there can be a pool of many queued recipe steps, covering many different dishes at once, and a single chef can pull from all of these. Do this fast enough, and it feels parallel. 

The concrete mechanism is that the OS scheduler fires every few milliseconds and says, _"stop what you're doing, save your place, move on to the next process."_ The CPU saves its current **context** and loads the context of the next process. This is called a **context switch**.[ Unlike humans](https://www.fastcompany.com/944128/worker-interrupted-cost-task-switching), CPUs are incredibly good at context switches. 

For example, run the below bash program:

```bash
# 8 CPU burning loops
for i in {1..8}; do 
	(while true; do :; done) & 
done
```

This just starts a set of 8 CPU-burning loops. Now run 

```bash 
top
```

You'll see all 8 processes consuming CPU simultaneously, with their assigned core constantly shifting (and a single core handling multiple processes at once). Read more about the `top` command's output [[#More on the `top` command|here]].

That's the scheduler redistributing work in real time. Remember to kill the jobs afterwards, or you'll drain your battery:

```bash 
kill $(jobs -p)
```

## Concurrency vs Parallelism

So far, we've been talking at the level of cooking multiple recipes at once, but we can take this further. 

It's also possible to complete multiple steps in the same recipe at once. 

Take a baking recipe that asks you to preheat the oven for $30$ minutes. You'd instinctively move on to other prep steps in the meantime rather than standing idle. This is **concurrency** - you have a single pool of tasks, and you move on to other work rather than blocking on a slow step.

But note the distinction between concurrency and true parallelism. True parallelism is still defined down to the micro-level. When you prep while the oven heats, you aren't still _doing_ the preheating - you've simply paused it and moved on. True parallelism would require two chefs: one managing the oven, another doing the prep, both working at the same instant.

## Threads

A **thread** is a single line of execution within a process. It is just a task list.  Every process has at least one, but processes can spawn multiple threads that execute **independently and in parallel**. Crucially, threads within the same process share the same memory, which makes passing data between them fast and straightforward.

Going back to our kitchen analogy, multi-threading is assigning a second chef to the same recipe. One could be dedicated to the icing, and another simultaneously handles the cake. Both are executing steps from the same recipe at the same instant, sharing the same workspace (RAM).

Why don't we just multi-thread everything? Two processes running on two separate cores are truly independent. If one crashes, the other is unaffected. However, a crashed thread can bring down the whole process. 

Take Chrome as an example. Each open tab is a thread within the same process. They share memory and can pass data between each other instantly, but they execute independently and can run on separate cores simultaneously. The trade-off is that a single misbehaving tab can take down your browser window.

## More on the `top` command 

A typical `top` output looks like this 

```bash
Processes: 487 total, 4 running, 483 sleeping
Load Avg: 3.42, 2.11, 1.87
CPU usage: 42.3% user, 8.1% sys, 49.6% idle
...
PID COMMAND %CPU TIME #TH #WQ #PORT MEM PURG CMPRS PGRP 1234 
```

Here's how to read the heading:

- `Processes: 487 total, 4 running, 483 sleeping`. The sleeping processes exist but are waiting for something (e.g. a keypress). The running ones are being actively executed by some core at this moment.
- `Load Avg` gives us the average number of processes **wanting** CPU time over the last $1, 5, 15$ minutes. In this case, we have had $3-4$ cores in use over the last minute. 
- `CPU usage` just says who's been burning the CPU. 

Of real interest is the process table. This gives us a row per process:

- `PID` is the process ID
- `COMMAND` is the program name
- `%CPU` is the percentage of a **single core** being used
- `TIME` is the total CPU time consumed since a process started
- `#TH` is the thread count
- `MEM` is the RAM being used by this process