+++
date = "2023-04-08"
draft = false
title = "ChatGPT代理"

+++

> 如果访问ChatGPT出现类似错误，说明你的IP已经被封禁限制访问了：）

*Access denied*   
You do not have access to chat.openai.com   
The site owner may have set restrictions that prevent you from accessing the site.

![](/images/2023-05-29-09-42-28.png)

在得知亲爹微软的Azure 的出口IP好用后，我拿出之前薅heroku羊毛的[FQ方案](https://github.com/ls0f/cracker)来薅一下Azure =_=

# 前提

* 已经有Chat OpenAI账号（sms-activate 收验证码）
* 拥有Azure账号并绑定了信用卡（国内VISA即可）
* 玩得转SwitchyOmega（很简单的）

# 创建容器

* [进入Azure免费服务](https://portal.azure.com/#view/Microsoft_Azure_Billing/FreeServicesBlade)页面  选择容器应用（有免费额度），创建容器
![](/images/2023-05-29-09-48-12.png)

* 需新建资源组和选择区域、新建容器应用环境
![](/images/2023-05-29-09-48-41.png)

* 设置容器应用信息（很重要，不要设置错）

镜像选择：`ls0f/cracker-server`   
环境变量SECRET 自己设置，在下一步很会用上  
![](/images/2023-05-29-09-49-40.png)
![](/images/2023-05-29-09-49-52.png)

* 创建资源，等待容器部署完成后跳转到资源页面

![](/images/2023-05-29-10-01-38.png)

拿到分配的访问地址，浏览器请求测试，正常会返回404页面，这个地址在下一步会用上   
![](/images/2023-05-29-09-50-15.png)

走到这一步，你已经成功了80%


# 本地代理

* 去[Github下载客户端](https://github.com/ls0f/cracker/releases)
![](/images/2023-05-29-09-51-41.png)

* 本地终端中，运行客户端程序

-addr 本地监听端口  
-raddr 容器访问地址（Azure分配的访问地址）  
-secret 秘钥（创建容器的时候设置的）  

示例  
```
./local -addr 127.0.0.1:1234 -raddr https://chatgpt.jollybush-7290e711.westus2.azurecontainerapps.io/  -secret chatgpt12345 -logtostderr -v=10
```
![](/images/2023-05-29-09-53-12.png)

* SwitchyOmega 新增代理配置

我的配置可供参考   

![](/images/2023-05-29-09-53-54.png)
>配置为上面命令行设置的监听端口

![](/images/2023-05-29-09-54-46.png)
>设置OpenAI域名走代理

# Haaaaappy Chat
![](/images/2023-05-29-09-55-48.png)