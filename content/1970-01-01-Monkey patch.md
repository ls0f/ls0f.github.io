title: Monkey patch
date: 1970-01-01
comments: true
categories: 
什么是Monkey patch呢？简单理解就是在程序运行时动态修改代码，而不是在磁盘上修改源代码。

那么Monkey patch有什么作用呢？[维基](https://en.wikipedia.org/wiki/Monkey_patch)上的解释是:
>＊ Replace methods/attributes/functions at runtime, e.g. to stub out a function >during testing;
>
>＊ Modify/extend behaviour of a third-party product without maintaining a >private copy of the source code;
>
>＊ Apply a patch at runtime to the objects in memory, instead of the source >code on disk;
>
>＊ Distribute security or behavioural fixes that live alongside the original >source code (an example of this would be distributing the fix as a plugin >for the Ruby on Rails platform).

Monkey patch的应用场景有哪些？我想到的主要是下面两点：

1，热升级。比如游戏行业中的不停服升级。      
2，hack第三方库。比如给第三方库打漏洞补丁、自定义功能。

善于打Monkey patch是Python程序员提高生产力、能力进阶的必备技能之一。

说一下我用到的一个场景。

2014-12-08，七牛的域名qiniudn.com被数字拦截。导致装有360的PC都不能访问qiniudn.com上的图片。我司也是受害者。我测试发现七牛默认提供的qbox.me 的域名是没有被拦截的。于是我紧急给tornado的模版函数打了一个Monkey patch，将网页模版里面qiniudn.com全部替换为qbox.me这个域名。

```
    def hot_fix_2014_12_08_patch():

        from tornado.template  import Template
        old_generate = Template.generate
        def hack_generate(self,**kwargs):
            html = old_generate(self,**kwargs)
            html = html.replace("yy.qiniudn.com", "xx.qbox.me")
            return html

        tornado.template.Template.generate = hack_generate

```

[stackoverflow上关于Monkey patch的讨论](http://stackoverflow.com/questions/5626193/what-is-a-monkey-patch)

![http://ww2.sinaimg.cn/large/79565610gw1etwwmkgxifj20jk0cw0v3.jpg](http://ww2.sinaimg.cn/large/79565610gw1etwwmkgxifj20jk0cw0v3.jpg) 

图片来自网络。
