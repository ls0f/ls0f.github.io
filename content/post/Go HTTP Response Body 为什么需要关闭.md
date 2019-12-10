+++
date = "2019-12-05"
draft = false
title = "Go HTTP Response Body 为什么需要关闭"

+++
当用Go发送一个Get请求的时候，会写类似下面的代码：
```
res, err := http.Get("http://mirrors.tencent.com")
if err != nil {
	return err
}
defer res.Body.Close()
...
```
写一个程序去验证下如果不对res.Body进行Close会发送什么。
```
package main

import (
	"io"
	"io/ioutil"
	"net/http"
	"os"
)
func req() {
	res, err := http.Get("http://mirrors.tencent.com")
	if err != nil {
		panic(err)
	}
	println(res.StatusCode)
}
func main()  {
	println("pid:", os.Getpid())
	for i:=0;i<10;i++{
		req()
	}
	io.CopyN(ioutil.Discard, os.Stdin, 1)
}

```
go run，然后通过lsof去看下进程打来了10个http连接：
```
⇒  lsof -p 20440 | grep http
test    20440 zhuo    6u     IPv4 0xd577b7664ae774b      0t0      TCP x.x.x.x:52444->mirrors.tencent.com:http (ESTABLISHED)
test    20440 zhuo    8u     IPv4 0xd577b7664ab70cb      0t0      TCP x.x.x.x:52445->mirrors.tencent.com:http (ESTABLISHED)
test    20440 zhuo    9u     IPv4 0xd577b765d38144b      0t0      TCP x.x.x.x:52446->mirrors.tencent.com:http (ESTABLISHED)
test    20440 zhuo   10u     IPv4 0xd577b76516ce74b      0t0      TCP x.x.x.x:52447->mirrors.tencent.com:http (ESTABLISHED)
test    20440 zhuo   11u     IPv4 0xd577b7664aa3dcb      0t0      TCP x.x.x.x:52448->mirrors.tencent.com:http (ESTABLISHED)
test    20440 zhuo   12u     IPv4 0xd577b764f1f7a4b      0t0      TCP x.x.x.x:52449->mirrors.tencent.com:http (ESTABLISHED)
test    20440 zhuo   13u     IPv4 0xd577b765f7ac74b      0t0      TCP x.x.x.x:52450->mirrors.tencent.com:http (ESTABLISHED)
test    20440 zhuo   14u     IPv4 0xd577b765fa93a4b      0t0      TCP x.x.x.x:52451->mirrors.tencent.com:http (ESTABLISHED)
test    20440 zhuo   15u     IPv4 0xd577b7653cf5a4b      0t0      TCP x.x.x.x:52452->mirrors.tencent.com:http (ESTABLISHED)
test    20440 zhuo   16u     IPv4 0xd577b764f2910cb      0t0      TCP x.x.x.x:52453->mirrors.tencent.com:http (ESTABLISHED)
```
从代码上看看究竟是怎么回事，http请求的发送和接收相关代码在这里，包括连接建立、连接池等 https://github.com/golang/go/blob/master/src/net/http/transport.go

http连接封装成了[`struct persistConn`](https://github.com/golang/go/blob/cdf3db5df6bdb68f696fb15cc657207efcf778ef/src/net/http/transport.go#L1728)，
看下http连接是如何建立的 https://github.com/golang/go/blob/cdf3db5df6bdb68f696fb15cc657207efcf778ef/src/net/http/transport.go#L1467
```
func (t *Transport) dialConn(ctx context.Context, cm connectMethod) (pconn *persistConn, err error) {
....
	pconn.br = bufio.NewReaderSize(pconn, t.readBufferSize())
	pconn.bw = bufio.NewWriterSize(persistConnWriter{pconn}, t.writeBufferSize())
    // 会起两个goroutine来对数据进行读写
	go pconn.readLoop()
	go pconn.writeLoop()
}
```
重点看下realLoop，是一个死循环，只要连接可用一直不会退出。
https://github.com/golang/go/blob/cdf3db5df6bdb68f696fb15cc657207efcf778ef/src/net/http/transport.go#L1903
```
    ...
	alive := true
	for alive {
		...
		waitForBodyRead := make(chan bool, 2)
		body := &bodyEOFSignal{
			body: resp.Body,
			earlyCloseFn: func() error {
				waitForBodyRead <- false
				<-eofc // will be closed by deferred call at the end of the function
				return nil

			},
			fn: func(err error) error {
				isEOF := err == io.EOF
				waitForBodyRead <- isEOF
				if isEOF {
					<-eofc // see comment above eofc declaration
				} else if err != nil {
					if cerr := pc.canceled(); cerr != nil {
						return cerr
					}
				}
				return err
			},
		}

		resp.Body = body
		select {
		case bodyEOF := <-waitForBodyRead:
			pc.t.setReqCanceler(rc.req, nil) // before pc might return to idle pool
			alive = alive &&
				bodyEOF &&
				!pc.sawEOF &&
				pc.wroteRequest() &&
				tryPutIdleConn(trace)
			if bodyEOF {
				eofc <- struct{}{}
			}
		case <-rc.req.Cancel:
			alive = false
			pc.t.CancelRequest(rc.req)
		case <-rc.req.Context().Done():
			alive = false
			pc.t.cancelRequest(rc.req, rc.req.Context().Err())
		case <-pc.closech:
			alive = false
		}

		testHookReadLoopBeforeNextRead()
	}
}
```
如果我们没有对Body进行Close或者没有把当前http请求的body读完，readLoop 一直会阻塞在select调用处，导致连接不能被复用，所以我上面发送的10个http请求没有调用Body Close，就会泄露20个goroutine。
官方文档明确说了
> When err is nil, resp always contains a non-nil resp.Body.
Caller should close resp.Body when done reading from it.

有兴趣的再研究一下代码可以发现：
* 有Body没有读完，就行Close的话，连接会被关闭，不会复用
* 如果读完了所有Body，可以不调用Close，连接也会被复用

所以最佳实践是：http请求发出后，如果没有错误，马上声明`defer res.Body.Close()`，避免资源泄露，然后尽量读完Body，好让连接复用。

```
res, err := http.Get("http://mirrors.tencent.com")
if err != nil {
	return
}
defer res.Body.Close() // 避免资源泄露
/*
处理逻辑，尽量读完Body，好让连接复用
io.Copy(ioutil.Discard, res.Body)
*/
...

```
