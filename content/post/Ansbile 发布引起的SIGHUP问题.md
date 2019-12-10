+++
date = "2018-07-12"
draft = false
title = "Ansible发布引起的SIGHUP问题" 
+++

# 0X01背景

最近通过ansible发布程序，出现线上故障。排查原因：ansible调用shell执行命令完毕后，程序收到`SIGHUP`信号。程序最开始是支持本地配置reload，后来一些经常变化的配置改成通过zk订阅来进行更新，免去频繁线上reload配置，但`SIGHUP`信号处理这个分支的代码未兼容zk更新配置，导致问题出现。

根本问题是为何会收到`SIGHUP`信号，在用ansible发布前，我都是上机手动执行restart脚本，然后登出，这个过程程序并不会收到`SIGHUP`信号。改成ansible却出现问题，整个发布playbook简化下来就下面一行命令：
```yaml
  tasks:

    - name: start app
      shell: service.sh restart
      register: run

    - debug: msg="{{ run.stdout_lines }}"
```
server.sh脚本的内容可参考这个[链接](https://github.com/fhd/init-script-template/blob/master/template)，主要命令是：
```bash
sudo $cmd >> "$stdout_log" 2>> "$stderr_log" &
```
对Linux作业控制了解的同学可能会模糊的知道：当终端断开的时候，程序会收到`SIGHUP`信号。但诡异的是：手动连接机器执行restart命令，然后登出不会触发`SIGHUP`信号给后台进程，通过ansible却会。

# 0X02 Linux进程

在进一步分析前，先回顾下Linux进程的基本知识。为了更容易理解和实现作业控制，Linux抽象了session和进程组（process group）。记住这几点就行

 - session是进程组的集合
 - 进程组是进程的集合
 - session leader是创建session的进程（setsid系统调用）
 - 进程组leader是创建组的进程（setpgid系统系统）
 - session只有一个前台进程组和若干个后台进程组

session可能有控制终端（control terminal），如/dev/ttyn、/dev/ptsn，常说的damon程序就没有。当session leader打开控制终端，同时就成为了终端的控制进程。

![image-20180914165128266](https://ws1.sinaimg.cn/large/79565610gy1fvcb57mqdpj20qt0nn43l.jpg)

# 0X03 SIGHUP

再梳理一下`SIGHUP`信号，什么时候程序会收到`SIGHUP`信号，是谁发送的信号。

## 0x01 内核发送SIGHUP

当控制进程失去终端后，内核会发送一个SIGHUP信号给控制进程。失去终端有下面两种情形：

- 终端驱动感知连接关闭（物理终端）
- 直接关闭视窗、网络断掉（虚拟终端）

向控制进程发送SIGHUP信号会引起链式反应，这会导致SIGHUP信号发送给其他进程。可能会由下面两种方式处理：

- 当控制进程是shell时，在shell退出前，它会将SIGHUP信号发送给它创建的所有任务
- 内核会向该终端会话的前台进程组成员发送SIGHUP信号

写个简单的程序测试：

```python
import signal
import os
import time

def handler(signum, frame):
    print 'Signal handler called with signal', signum

print "pid:%s" % os.getpid()
signal.signal(signal.SIGHUP, handler)
while 1:
    time.sleep(10240)

```

```shell
[root@VM_137_43_centos ~]# echo $$
7394
[root@VM_137_43_centos ~]# python test.py 
pid:7473
```

关闭视窗前，用strace捕获控制进程(shell)`7394`和前台进程`7473`的信号。
控制进程收到了来自内核的`SIGHUP`信号，然后转发给了前台进程组，最后给自己再次发送了`SIGHUP`信号。

```shell
[root@VM_137_43_centos ~]# strace -e trace=signal -p7394
Process 7394 attached
--- SIGHUP {si_signo=SIGHUP, si_code=SI_KERNEL, si_value={int=2640381528, ptr=0x7fc69d610658}} ---
--- SIGCONT {si_signo=SIGCONT, si_code=SI_KERNEL, si_value={int=2640381528, ptr=0x7fc69d610658}} ---
rt_sigreturn()                          = -1 EINTR (Interrupted system call)
kill(4294959823, SIGHUP)                = 0
rt_sigprocmask(SIG_BLOCK, [CHLD TSTP TTIN TTOU], [CHLD], 8) = 0
rt_sigprocmask(SIG_SETMASK, [CHLD], NULL, 8) = 0
rt_sigaction(SIGHUP, {SIG_DFL, [], SA_RESTORER, 0x7fc28611a250}, {0x456a40, [HUP INT ILL TRAP ABRT BUS FPE USR1 SEGV USR2 PIPE ALRM TERM XCPU XFSZ VTALRM SYS], SA_RESTORER, 0x7fc28611a250}, 8) = 0
kill(7394, SIGHUP)                      = 0
--- SIGHUP {si_signo=SIGHUP, si_code=SI_USER, si_pid=7394, si_uid=0} ---
+++ killed by SIGHUP +++

```

*这里需要注意shell的kill指令是`kill(4294959823, SIGHUP)`实际是kill(-7473, SIGHUP)`。strace显示出来的是无符号数。无符号数4294959823和-7473的16进制都是`**0xFFFFE2CF**,这里也说明shell是对整个进程组发送信号*

前台进程分别收到了控制进程和内核发送的`SIGHUP`信号

```shell
Process 7473 attached
--- SIGWINCH {si_signo=SIGWINCH, si_code=SI_KERNEL, si_value={int=607876696, ptr=0x7f69243b7658}} ---
--- SIGWINCH {si_signo=SIGWINCH, si_code=SI_KERNEL, si_value={int=607876696, ptr=0x7f69243b7658}} ---
--- SIGWINCH {si_signo=SIGWINCH, si_code=SI_KERNEL, si_value={int=607876696, ptr=0x7f69243b7658}} ---
--- SIGHUP {si_signo=SIGHUP, si_code=SI_USER, si_pid=7394, si_uid=0} ---
rt_sigreturn()                          = -1 EINTR (Interrupted system call)
--- SIGHUP {si_signo=SIGHUP, si_code=SI_KERNEL, si_value={int=607876696, ptr=0x7f69243b7658}} ---
--- SIGCONT {si_signo=SIGCONT, si_code=SI_KERNEL, si_value={int=607876696, ptr=0x7f69243b7658}} ---
rt_sigreturn()                          = -1 EINTR (Interrupted system call)
```
这里可以注意到内核发送`SIGHUP`信号后，还会发送一个`SIGCOUT`信号确保进程重新运行。
内核发送SIGHUP的另一个场景：是当进程组变为[孤儿进程组](https://stackoverflow.com/questions/31916561/must-a-process-group-have-a-running-leader-process/31919569#31919569)时，并且进程组中有停止的任务

```shell
import os
import signal
import time

pid = os.fork()

if pid > 0:
    time.sleep(15)
    print "parent exit"
else:
    pid = os.fork()
    print "pid is %s" % os.getpid()
    if pid > 0:
    	#进程1进入stop状态
        os.kill(os.getpid(), signal.SIGSTOP)
    else:
    	#测试进程2能否收到SIGHUP
        time.sleep(20)
    print "child exit"


[root@VM_137_43_centos ~]# python test2.py 
pid is 15423
pid is 15424
parent exit
```

```shell
[root@VM_137_43_centos ~]#  strace -e trace=signal -p15424
Process 15424 attached
--- SIGHUP {si_signo=SIGHUP, si_code=SI_KERNEL, si_value={int=1655117400, ptr=0x7f3962a71658}} ---
+++ killed by SIGHUP +++

[root@VM_137_43_centos ~]# strace -e trace=signal -p15423
Process 15423 attached
--- stopped by SIGSTOP ---
--- SIGHUP {si_signo=SIGHUP, si_code=SI_KERNEL, ...} ---
+++ killed by SIGHUP +++

```

## 0x02  SHELL对SIGUP信号处理

shell会发送`SIGHUP`信号给前台进程，对后台进程的处理分两种case：

- 01 shell正常logout

- 02 收到内核SIGHUP信号

正常logout后， 后台进程还在，说明shell没有发送SIGHUP信号。sleep命令连接的终端被关闭了（pts/13 - ?）。

```shell
[root@VM_137_43_centos ~]# sleep 10240 &
[1] 9309
[root@VM_137_43_centos ~]# ps -ef | grep 9309
root      9309  9117  0 12:44 pts/13   00:00:00 sleep 10240
root      9316  9117  0 12:45 pts/13   00:00:00 grep --color=auto 9309
[root@VM_137_43_centos ~]# exit
# login
[root@VM_137_43_centos ~]# ps -ef | grep 9309
root      9309     1  0 12:44 ?        00:00:00 sleep 10240
root      9374  9344  0 12:45 pts/12   00:00:00 grep --color=auto 9309
```

关闭视窗，内核发送`SIGHUP`给控制进程，然后转发给后台进程。

```shell
[root@VM_137_43_centos ~]# echo $$
10599
[root@VM_137_43_centos ~]# sleep 10240 &
[1] 10622
# 关闭视窗
[root@VM_137_43_centos ~]# strace -e trace=signal -p10622
Process 10622 attached
--- SIGHUP {si_signo=SIGHUP, si_code=SI_USER, si_pid=10599, si_uid=0} ---
+++ killed by SIGHUP +++
```

看一下bash的文档：

> ​	The  shell exits by default upon receipt of a SIGHUP.  Before exiting, an interactive shell resends the SIGHUP to all jobs, running or stopped.  Stopped jobs are sent SIGCONT to ensure that they receive the SIGHUP.  To prevent the shell from sending the signal to a particular job, it should be removed from the jobs table with the disown builtin (see SHELL BUILTIN COMMANDS below) or marked to not receive SIGHUP using disown -h.
>
> ​       If the huponexit shell option has been set with shopt, bash sends a SIGHUP to all jobs when an interactive login shell exits.
>
> ​      If bash is waiting for a command to complete and receives a signal for which a trap has been set, the trap will not be executed until the command completes.  When bash is waiting for an asynchronous  command  via  the  wait
>
> ​       builtin, the reception of a signal for which a trap has been set will cause the wait builtin to return immediately with an exit status greater than 128, immediately after which the trap is executed

所以如果通过shopt设置了huponexit选项`shopt -s huponexit`，case1和case2的效果是一样的。

这里有两点需要注意：

当shell启动的进程退出后，进程组会从shell的任务列表删去，fork出来的子进程不会收到shell的SIGHUP信号。

```bash
#!/bin/bash
sleep 10240 &
```

如果关闭视窗，sleep命令依然会在后台运行。所以如果不是shell直接fork启动，而是在脚本里面启动的话，是不需要`nohup`的。

如果进程改变了进程组ID，并且进程组ID不是由此shell创建的，也不会收到SIGHUP信号。

```shell
[root@VM_137_43_centos ~]# cat test3.py 
import os,time

def pp(tip):
    print "%s pid:%s, ppid:%s, pgid:%s" % (tip, os.getpid(), os.getppid(), os.getpgid(os.getpid()))

if os.fork() > 0:
    pp("parent")
    time.sleep(10240)
else:
    pp("child")
    os.setpgid(0, 0)
    pp("child")
    time.sleep(10240)
    
[root@VM_137_43_centos ~]# python test3.py 
parent pid:18292, ppid:18260, pgid:18292
child pid:18293, ppid:18292, pgid:18292
child pid:18293, ppid:18292, pgid:18293 #pgid变化

[root@VM_137_43_centos ~]#  strace -e trace=signal -p18292 -p 18293
Process 18292 attached
Process 18293 attached
[pid 18292] --- SIGWINCH {si_signo=SIGWINCH, si_code=SI_KERNEL, si_value={int=3431224920, ptr=0x7fbfcc845658}} ---
[pid 18292] --- SIGWINCH {si_signo=SIGWINCH, si_code=SI_KERNEL, si_value={int=3431224920, ptr=0x7fbfcc845658}} ---
[pid 18292] --- SIGWINCH {si_signo=SIGWINCH, si_code=SI_KERNEL, si_value={int=3431224920, ptr=0x7fbfcc845658}} ---
[pid 18292] --- SIGHUP {si_signo=SIGHUP, si_code=SI_USER, si_pid=18260, si_uid=0} ---
[pid 18292] +++ killed by SIGHUP +++

```

改变了进程组ID的子进程没有收到`SIGHUP`信号。
结合上面shell对整个进程组发送信号，说明shell作业控制是基于进程组，进程组是job的抽象。

PS 这里我只是测试了bash的表现情况，各家shell可能不一致，但基本一致。

## 0x03  SIGHUP总结

什么时候内核会发送SIGHUP信号

- 当终端关闭时，发送SIGHUP信号给终端控制进程（通常是shell）
- 当终端控制进程关闭时，发送SIGHUP给当前会话的前台进程组
- 当进程组变为孤儿进程时并且还有stop状态的任务时，发送SIGHUP给孤儿进程组

什么时候shell发送SIGHUP信号

- 当收到内核SIGHUP信号时，发送SIGHUP给所有前后台进程组
- 当正常logout时，发送SIGHUP给前台进程组，通过`huponexit`配置是否发送给后台进程组

# 0X04 Ansible

来看下Ansible发布到底做了什么。playbook测试，为了执行完test.sh后，sleep 60秒，保留现场。

```yaml

  tasks:

    - name: start app
      shell: /root/test.sh && sleep 60
      register: run

    - debug: msg="{{ run.stdout_lines }}"
```

```
#!/bin/sh
# test.sh

sleep 10240 >> /dev/null 2>> /dev/null &
pid=$!
echo "$pid success..."
```

可以看到shell命令是编码成python脚本，然后在python脚本fork执行shell命令。最重要的因为是以非交互式shell运行的命令，所有的命令都归属于同一个进程组。前面说了连接断开后，内核会发送`SIGHUP`信号给前台进程组。

```shell
UID        PID  PPID  PGID   SID  C STIME TTY          TIME CMD
root     10069 10057 10069 10069  0 16:12 pts/8    00:00:00 /bin/sh -c /usr/bin/python /root/.ansible/tmp/ansible-tmp-1537085564.57-12697012229826/command.py; rm -rf "/root/.ansible/tmp/ansible-tmp-1537085564.57-12697012229826/" > /dev/null 2>&1 
 sleep 0
root     10085 10069 10069 10069  0 16:12 pts/8    00:00:00 /usr/bin/python /root/.ansible/tmp/ansible-tmp-1537085564.57-12697012229826/command.py
root     10086 10085 10069 10069  0 16:12 pts/8    00:00:00 /usr/bin/python /tmp/ansible_P3TTAF/ansible_module_command.py 
root     10087 10086 10069 10069  0 16:12 pts/8    00:00:00 /bin/sh -c /root/test.sh && sleep 60
root     10089     1 10069 10069  0 16:12 pts/8    00:00:00 sleep 10240

```
playbook执行完后，10089进程收到了来自内核的`SIGHUP`信号。
```
[pid 10089] +++ exited with 0 +++
--- SIGHUP {si_signo=SIGHUP, si_code=SI_KERNEL, si_value={int=0, ptr=0x7fa200000000}} ---
+++ killed by SIGHUP +++
```
到这里就真相大白了。解决办法：playbook里面调用setsid创建新会话。`setsid /root/test.sh`

# 0X05 总结思考

线上操作保持敬畏之心。批量操作一定要灰度，观察验证、观察验证、观察验证。

# 0X06 参考

[0x01]The Linux Programming Interface   
[0x02]https://stackoverflow.com/questions/4298741/how-bash-handles-the-jobs-when-logout    
[0x03]https://stackoverflow.com/questions/32780706/does-linux-kill-background-processes-if-we-close-the-terminal-from-which-it-has
