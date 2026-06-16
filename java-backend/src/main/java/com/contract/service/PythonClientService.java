package com.contract.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

@Slf4j
@Service
@RequiredArgsConstructor
public class PythonClientService {

    private static final ObjectMapper mapper = new ObjectMapper();
    private final HttpClient httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .build();

    @org.springframework.beans.factory.annotation.Value("${python.service.url}")
    private String pythonUrl;
    private final ExecutorService sseExecutor = Executors.newCachedThreadPool();

    /**
     * 向 Python 服务发起审核请求，返回 review_id。
     */
    @SuppressWarnings("unchecked")
    public String startReview(Map<String, Object> payload) {
        try {
            String json = mapper.writeValueAsString(payload);
            log.info("Python 请求: {}", json);

            var request = HttpRequest.newBuilder()
                    .uri(URI.create(pythonUrl + "/api/reviews"))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(json, StandardCharsets.UTF_8))
                    .build();

            var response = httpClient.send(request,
                    HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));

            log.info("Python 响应: status={}, body={}", response.statusCode(), response.body());

            if (response.statusCode() != 200) {
                throw new RuntimeException("Python 返回错误: " + response.body());
            }

            Map<String, Object> result = mapper.readValue(response.body(), Map.class);
            return (String) result.get("review_id");
        } catch (Exception e) {
            log.error("调用 Python 失败", e);
            throw new RuntimeException("Python 服务调用失败: " + e.getMessage(), e);
        }
    }

    /**
     * 查询 Python 审核状态。
     */
    public Map<String, Object> getReviewStatus(String reviewId) {
        try {
            var request = HttpRequest.newBuilder()
                    .uri(URI.create(pythonUrl + "/api/reviews/" + reviewId + "/status"))
                    .GET()
                    .build();
            var response = httpClient.send(request,
                    HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            return mapper.readValue(response.body(), Map.class);
        } catch (Exception e) {
            log.error("查询审核状态失败", e);
            throw new RuntimeException("Python 服务调用失败: " + e.getMessage(), e);
        }
    }

    /**
     * 获取 Python 审核报告。
     */
    public Map<String, Object> getReviewReport(String reviewId) {
        try {
            var request = HttpRequest.newBuilder()
                    .uri(URI.create(pythonUrl + "/api/reviews/" + reviewId + "/report"))
                    .GET()
                    .build();
            var response = httpClient.send(request,
                    HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            return mapper.readValue(response.body(), Map.class);
        } catch (Exception e) {
            log.error("获取审核报告失败", e);
            throw new RuntimeException("Python 服务调用失败: " + e.getMessage(), e);
        }
    }

    /**
     * 获取 Markdown 报告原文。
     */
    public String getReviewMarkdown(String reviewId) {
        try {
            var request = HttpRequest.newBuilder()
                    .uri(URI.create(pythonUrl + "/api/reviews/" + reviewId + "/report/markdown"))
                    .GET()
                    .build();
            var response = httpClient.send(request,
                    HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() != 200) {
                throw new RuntimeException("Markdown 报告获取失败: " + response.body());
            }
            return response.body();
        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            log.error("获取 Markdown 报告失败", e);
            throw new RuntimeException("Python 服务调用失败: " + e.getMessage(), e);
        }
    }

    /**
     * 取消 Python 审核。
     */
    public void cancelReview(String reviewId) {
        try {
            var request = HttpRequest.newBuilder()
                    .uri(URI.create(pythonUrl + "/api/reviews/" + reviewId))
                    .DELETE()
                    .build();
            httpClient.send(request, HttpResponse.BodyHandlers.discarding());
        } catch (Exception e) {
            log.error("取消审核失败", e);
        }
    }

    /**
     * SSE 中继: 订阅 Python SSE 并转发为 Spring SseEmitter。
     */
    public SseEmitter streamReview(String reviewId) {
        SseEmitter emitter = new SseEmitter(30 * 60 * 1000L);

        sseExecutor.execute(() -> {
            try {
                var request = HttpRequest.newBuilder()
                        .uri(URI.create(pythonUrl + "/api/reviews/" + reviewId + "/stream"))
                        .GET()
                        .build();

                var response = httpClient.send(request,
                        HttpResponse.BodyHandlers.ofInputStream());

                try (var reader = new BufferedReader(
                        new InputStreamReader(response.body(), StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        if (line.startsWith("data: ")) {
                            String data = line.substring(6);
                            emitter.send(SseEmitter.event().data(data));
                        }
                    }
                }
                emitter.complete();
            } catch (Exception e) {
                log.error("SSE 中继失败: reviewId={}", reviewId, e);
                emitter.completeWithError(e);
            }
        });

        emitter.onCompletion(() -> log.info("SSE 完成: reviewId={}", reviewId));
        emitter.onTimeout(() -> log.warn("SSE 超时: reviewId={}", reviewId));
        emitter.onError(e -> log.error("SSE 错误: reviewId={}", reviewId, e));

        return emitter;
    }
}
