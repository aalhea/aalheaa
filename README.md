# 阿里云Markdown翻译 V1.0
阿里云Markdown翻译 V1.0,适用各类文档类型

了解到很多情况下,AI工具和在线翻译网站,无法满足大批量md，txt，docx等常见文档内容.
这里结合阿里云api调用,实现常见文档翻译效果,并有效处理对应格式文本确保翻译效果可控.

## 阿里云api

1. 注册并登陆阿里云
2. [申请通用版翻译引擎](https://www.aliyun.com/product/ai/base_alimt?source=5176.11533457&userCode=wsnup3vv)(每月100 万字符免费额度)
3. 开通后 进去控制台，鼠标悬停在右上角用户头像
4. 点击**AccessKey 管理**
![image](https://github.com/user-attachments/assets/e57cae15-4eca-4c1f-872c-192c2a1fcd8c)

## 架构原理

- 翻译器类(Translator): 负责协调整个翻译流程，是系统的中心控制器
- 文本解析器(Parser): 使用正则表达式识别和处理不同类型的文本内容
- 并发执行器(Executor): 基于ThreadPoolExecutor实现多线程并发翻译
- API客户端(APIClient): 封装与阿里云翻译API的通信

- 模块化设计: 各功能组件间低耦合，便于维护和扩展
- 并发处理: 通过线程池实现高效翻译，大幅提升处理速度
- 智能分析: 能识别代码块、链接等特殊内容，保持格式不变
- 错误处理: 完善的异常捕获与日志记录机制
- 可配置性: 支持多种参数配置，适应不同翻译需求

## 使用文档

usage: main.py [-h] -f FILE [-o OUTPUT] [-s SOURCE] [-t TARGET] [--threads THREADS] [--batch-size BATCH_SIZE]
               [--interval INTERVAL]

阿里云机器翻译工具 - 支持Markdown格式翻译

optional arguments:
  -h, --help            show this help message and exit
  -f FILE, --file FILE  要翻译的输入文件路径
  -o OUTPUT, --output OUTPUT
                        翻译结果输出文件路径 (默认为: <输入文件名>_translated.<扩展名>)
  -s SOURCE, --source SOURCE
                        源语言代码 (默认: auto)
  -t TARGET, --target TARGET
                        目标语言代码 (默认: zh)
  --threads THREADS     并发线程数 (默认: 20)
  --batch-size BATCH_SIZE
                        批处理大小 (默认: 50)
  --interval INTERVAL   请求间隔时间，秒 (默认: 0.1)
![image](https://github.com/user-attachments/assets/9d5c40cb-86e8-407f-b319-917afb79a847)

## 翻译效果
![image](https://github.com/user-attachments/assets/60166735-aae6-4d37-9bba-1d2d61d58f0b)
![image](https://github.com/user-attachments/assets/631679ac-22ff-4ad1-8957-d61f2fcd603a)

