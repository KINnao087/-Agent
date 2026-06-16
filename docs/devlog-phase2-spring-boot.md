# Phase 2 开发日志：Spring Boot 后端

> 日期: 2026-06-15
> 目标: 为合同审核平台搭建 Java 后端壳，提供用户认证 + 合同 CRUD + Python AI 桥接

---

## 做了什么

### 1. 项目骨架

在 `java-backend/` 下新建 Spring Boot 3.3.5 + Maven 项目，Java 17。

**依赖选型：**

| 类别 | 技术 | 理由 |
|------|------|------|
| Web | spring-boot-starter-web | 嵌入式 Tomcat |
| 安全 | spring-boot-starter-security | 认证授权 |
| 数据库 | spring-boot-starter-data-jpa + mysql-connector-j | ORM + MySQL |
| JWT | jjwt 0.12.6 | 无状态令牌 |
| 工具 | Lombok | 减少样板代码 |
| 校验 | spring-boot-starter-validation | 请求参数校验 |

### 2. 文件清单（20 个源文件）

```
java-backend/src/main/java/com/contract/
├── ContractApplication.java           # Spring Boot 启动类
├── config/
│   ├── SecurityConfig.java           # JWT 无状态认证配置
│   ├── CorsConfig.java               # 跨域 (允许 Vue 调用)
│   └── RestClientConfig.java         # RestClient Bean (连 Python)
├── security/
│   ├── JwtTokenProvider.java         # JWT 生成/验证/解析
│   ├── JwtAuthenticationFilter.java  # 从 Header 提取 JWT
│   └── UserDetailsServiceImpl.java   # 加载用户信息
├── entity/
│   ├── User.java                     # users 表 (id, username, email, password_hash)
│   └── Contract.java                 # contracts 表 (id, user_id, title, file_path, review_id, status)
├── repository/
│   ├── UserRepository.java           # JPA 接口
│   └── ContractRepository.java       # JPA 接口
├── dto/
│   ├── LoginRequest.java             # record: email + password
│   ├── RegisterRequest.java          # record: username + email + password
│   ├── AuthResponse.java             # record: token + userId + username + email
│   ├── ContractUploadRequest.java    # record: title + filePath
│   └── ContractResponse.java         # record, 带 from(Contract) 工厂方法
├── service/
│   ├── AuthService.java              # 注册/登录/当前用户
│   ├── ContractService.java          # 合同 CRUD + 审核调度
│   └── PythonClientService.java      # HTTP 调用 Python + SSE 中继
└── controller/
    ├── AuthController.java           # /api/auth/*
    └── ContractController.java       # /api/contracts/*
```

### 3. 架构设计要点

**认证流程：**
```
1. 用户 POST /api/auth/register → BCrypt 加密密码 → 入库 → 返回 JWT
2. 用户 POST /api/auth/login → 验证密码 → 返回 JWT
3. 后续请求 Header: Authorization: Bearer <token>
4. JwtAuthenticationFilter 拦截 → 解析 JWT → 注入 SecurityContext
5. Controller 从 Authentication.getName() 取 userId
```

**SSE 中继逻辑：**
```
前端 EventSource → Java SseEmitter → Python /api/reviews/{id}/stream
                                        ↓ SSE (text/event-stream)
                                    Java 逐行读 → emitter.send()
```

用 `java.net.http.HttpClient`（Java 11+ 内置）替代 `RestClient` 做 SSE 读取，因为 `RestClient` 不支持流式消费。

**数据库表：**
- `users`: id, username(unique), email(unique), password_hash, created_at, updated_at
- `contracts`: id, user_id(FK), title, file_path, review_id, status(enum), created_at, updated_at

Hibernate `ddl-auto: update` 自动建表/更新表结构。

---

## 遇到了什么难题

### 难题 1：Maven 使用的 Java 版本不对

**现象：**
```
Fatal error compiling: 错误: 不支持发行版本 21
```

**原因：** `pom.xml` 写 `<java.version>21</java.version>`，但 Maven 绑定的是 `JAVA_HOME` 里的 Java 17（`mvn -version` 显示 Java 17.0.7）。

**解决：** 改为 `<java.version>17</java.version>`。项目没用到 Java 21 特性，降级无影响。

### 难题 2：MySQL 密码错误

**现象：**
```
Access denied for user 'root'@'localhost' (using password: YES)
```

**原因：** `application.yml` 写 `password: root`，但实际密码是 `zjj2005225`。

**解决：** 用 `mysql -u root -p"密码" -e "SELECT 1"` 逐个尝试，确认是纯小写 `zjj2005225`。

### 难题 3：Map.of() 类型推断失败

**现象：**
```
Map<String,String>无法转换为Map<String,Object>
```

**原因：** `Map.of("key1", "string_value1", "key2", "string_value2")` 时 Java 将所有值推断为 `String`，但 `pythonClient.startReview()` 的参数类型是 `Map<String, Object>`。

**解决：** 改为 `new HashMap<String, Object>()` + `put()`，显式控制泛型。

---

## 验证结果

| 测试项 | 命令 | 结果 |
|--------|------|------|
| 编译 | `mvn compile` | ✅ |
| 启动 | `mvn spring-boot:run` | ✅ 8080 端口，3 秒启动 |
| 注册 | `curl POST /api/auth/register` | ✅ 返回 JWT |
| 登录 | `curl POST /api/auth/login` | ✅ 返回 JWT |
| 建表 | Hibernate `ddl-auto: update` | ✅ users + contracts 自动创建 |

---

## 后续待办

- 文件上传接口（当前 `filePath` 只是字符串，需要 `MultipartFile`）
- 全局异常处理（`@ControllerAdvice`）
- 审核状态回调（Python 完成后通知 Java 更新 `contracts.status`）
