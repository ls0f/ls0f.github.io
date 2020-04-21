+++
date = "2020-04-21"
draft = false
title = "Go代理10S超时"

+++

### 背景   
机器通过代理去请求，请求会触发超时，稳定在10S多一点。

### 分析

几个现象：
* 不通过代理机器访问没问题
* 代理机器直接访问也没有问题
* 只有通过代理访问才会触发10S超时

首先，抓个包看下：

![img](/images/代理10S超时.jpeg)

抓包能看出：

* 客户端和代理服务器握手和第一个connect请求都没问题
* 代理服务器在和目标机器建立连接的时候就花了10S，然后才响应connect请求
* 后面的数据包交互很快

猜测是代理机器的问题，但是在代理机器用curl去访问目标机器也没问题，难道是代理程序问题？   
想到之前有看到过一篇文章，go dns触发超时，难道是DNS问题？

为了快速解决验证问题，马上将DNS换成网管提供的最新IP，发现超时问题确实解决了。

来看看Go是怎么解析DNS，为什么超时是10S。  

```
func (r *Resolver) lookupHost(ctx context.Context, host string) (addrs []string, err error) {
    order := systemConf().hostLookupOrder(r, host)
    if !r.preferGo() && order == hostLookupCgo {
        if addrs, err, ok := cgoLookupHost(ctx, host); ok {
            return addrs, err
        }
        // cgo not available (or netgo); fall back to Go's DNS resolver
        order = hostLookupFilesDNS
    }
    return r.goLookupHostOrder(ctx, host, order)
```

Go通过不同环境、配置来采取是用cgo还是pure go来解析DNS。  

如果cgo解析失败，尝试用pure go解析。darwin默认强制使用cgo解析，linux使用pure go。当然你也可以通过GODEBUG来改：

```
⇒  GODEBUG=netdns=go+2 go run test.go
go package net: GODEBUG setting forcing use of Go's resolver
go package net: hostLookupOrder(baidu.com) = files,dns
2020/04/21 22:13:22 [39.156.69.79 220.181.38.148]
```

看看pure go是怎么解析的：


```
// Do a lookup for a single name, which must be rooted
// (otherwise answer will not find the answers).
func (r *Resolver) tryOneName(ctx context.Context, cfg *dnsConfig, name string, qtype dnsmessage.Type) (dnsmessage.Parser, string, error) {
    var lastErr error
    serverOffset := cfg.serverOffset()
    sLen := uint32(len(cfg.servers))

    n, err := dnsmessage.NewName(name)
    if err != nil {
        return dnsmessage.Parser{}, "", errCannotMarshalDNSMessage
    }
    q := dnsmessage.Question{
        Name:  n,
        Type:  qtype,
        Class: dnsmessage.ClassINET,
    }

    for i := 0; i < cfg.attempts; i++ {
        for j := uint32(0); j < sLen; j++ {
            server := cfg.servers[(serverOffset+j)%sLen]

            p, h, err := r.exchange(ctx, server, q, cfg.timeout, cfg.useTCP)
            ...
    }
```

可以看出每个DNS server在timeout内没返回，就会尝试下一个server，直到尝试attempts次，attempts默认是2，timeout默认是5S。
```
// See resolv.conf(5) on a Linux machine.
func dnsReadConfig(filename string) *dnsConfig {
    conf := &dnsConfig{
        ndots:    1,
        timeout:  5 * time.Second,
        attempts: 2,
    }
```

可以写个简单的程序验证下： 
```
package main

import "net"
import "log"

func main(){
    res, err := net.LookupHost("baidu.com")
    if err != nil {
        log.Fatal(err)
        return
    }
    log.Printf("%v", res)
}

```

DNS修改为:
```
options timeout:5 attempts:3
nameserver 1.1.1.1
nameserver 2.2.2.2
nameserver 3.3.3.3
```
DNS都不会通，正常程序会45S（5x3x3）后会失败退出：

```
[root@VM_15_30_centos ~]# time GODEBUG=netdns=go+3 go run main.go
go package net: GODEBUG setting forcing use of Go's resolver
go package net: hostLookupOrder(baidu.com) = files,dns
2020/04/21 22:38:01 lookup baidu.com on 3.3.3.3:53: read udp 192.168.1.2:58704->3.3.3.3:53: i/o timeout
exit status 1

real    0m45.259s
user    0m0.240s
sys 0m0.040s
```

* PS：另外DNS最多配置3个，我发现有的同学配置了很多个，但其实只有前面3个才生效。

go也是按标准来实现的：

```
        case "nameserver": // add one name server
            if len(f) > 1 && len(conf.servers) < 3 { // small, but the standard limit
                // One more check: make sure server name is
                // just an IP address. Otherwise we need DNS
                // to look it up.
              ...
            }
```

到这里可以判断出：之前代理机器resolv.conf前面两台DNS不能正常解析，第三台DNS是好的。所以才触发了10S超时。  


另外pure go的DNS是没有cache的，而且net.Dial里面的Resolver是一个struct，不是interface，不方便去做替换。