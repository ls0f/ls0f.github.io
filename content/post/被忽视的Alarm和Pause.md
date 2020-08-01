+++
date = "2020-08-01"
draft = false
title = "被忽视的Alarm和Pause"

+++

>在软件工具和生态越来越复杂的今天，我们往往容易忽视一些内核提供的非常有用的函数。  
>Alarm和Pause就是其中之列。

## Alarm

有时候我们需要给程序加运行时间控制，很多人会用ps来检测或者用timeout命令来运行。  
Alarm函数也适合干这个事情。

```
import signal

signal.alarm(1)

while 1:
    pass
```

上面调用alarm(1)，表示要内核会在1s后给程序发SIGALARM信号，此信号的默认行为是终止程序，当然  
我们可以捕获信号做更多事情。alram精度是秒，但已经满足我们大部分需求了。

## Pause

有时写程序调试时，希望运行完后不要退出，保留现场，这个时候可以用pause，使程序进入sleep状态。
当调试完毕的时候，再crt+c退出。

```
import signal
# debug here
signal.pause()
```

## Links
[Alarm](https://man7.org/linux/man-pages/man2/alarm.2.html)  
[Pause](https://man7.org/linux/man-pages/man2/pause.2.html)