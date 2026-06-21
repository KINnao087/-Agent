package com.contract.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
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

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private final HttpClient httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .build();

    @Value("${python.service.url}")
    private String pythonUrl;

    private final ExecutorService sseExecutor = Executors.newCachedThreadPool();

    @SuppressWarnings("unchecked")
    public String startReview(Map<String, Object> payload) {
        try {
            String json = MAPPER.writeValueAsString(payload);
            log.info("Python request: {}", json);

            var request = HttpRequest.newBuilder()
                    .uri(URI.create(pythonUrl + "/api/reviews"))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(json, StandardCharsets.UTF_8))
                    .build();

            var response = httpClient.send(
                    request,
                    HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8)
            );

            log.info("Python response: status={}, body={}", response.statusCode(), response.body());

            if (response.statusCode() != 200) {
                throw new RuntimeException("Python returned error: " + response.body());
            }

            Map<String, Object> result = MAPPER.readValue(response.body(), Map.class);
            return (String) result.get("review_id");
        } catch (Exception e) {
            log.error("Failed to call Python start review", e);
            throw new RuntimeException("Python service call failed: " + e.getMessage(), e);
        }
    }

    public Map<String, Object> getReviewStatus(String reviewId) {
        try {
            var request = HttpRequest.newBuilder()
                    .uri(URI.create(pythonUrl + "/api/reviews/" + reviewId + "/status"))
                    .GET()
                    .build();
            var response = httpClient.send(
                    request,
                    HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8)
            );
            return MAPPER.readValue(response.body(), Map.class);
        } catch (Exception e) {
            log.error("Failed to fetch review status", e);
            throw new RuntimeException("Python service call failed: " + e.getMessage(), e);
        }
    }

    public Map<String, Object> getReviewReport(String reviewId) {
        try {
            var request = HttpRequest.newBuilder()
                    .uri(URI.create(pythonUrl + "/api/reviews/" + reviewId + "/report"))
                    .GET()
                    .build();
            var response = httpClient.send(
                    request,
                    HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8)
            );
            return MAPPER.readValue(response.body(), Map.class);
        } catch (Exception e) {
            log.error("Failed to fetch review report", e);
            throw new RuntimeException("Python service call failed: " + e.getMessage(), e);
        }
    }

    public String getReviewMarkdown(String reviewId) {
        try {
            var request = HttpRequest.newBuilder()
                    .uri(URI.create(pythonUrl + "/api/reviews/" + reviewId + "/report/markdown"))
                    .GET()
                    .build();
            var response = httpClient.send(
                    request,
                    HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8)
            );

            if (response.statusCode() == 404) {
                throw new ResponseStatusException(
                        HttpStatus.NOT_FOUND,
                        "Markdown report not generated yet"
                );
            }
            if (response.statusCode() != 200) {
                throw new ResponseStatusException(
                        HttpStatus.BAD_GATEWAY,
                        "Markdown report fetch failed: " + response.body()
                );
            }

            return response.body();
        } catch (ResponseStatusException e) {
            throw e;
        } catch (Exception e) {
            log.error("Failed to fetch markdown report", e);
            throw new RuntimeException("Python service call failed: " + e.getMessage(), e);
        }
    }

    public void cancelReview(String reviewId) {
        try {
            var request = HttpRequest.newBuilder()
                    .uri(URI.create(pythonUrl + "/api/reviews/" + reviewId))
                    .DELETE()
                    .build();
            httpClient.send(request, HttpResponse.BodyHandlers.discarding());
        } catch (Exception e) {
            log.error("Failed to cancel review", e);
        }
    }

    public SseEmitter streamReview(String reviewId) {
        SseEmitter emitter = new SseEmitter(30 * 60 * 1000L);

        sseExecutor.execute(() -> {
            try {
                var request = HttpRequest.newBuilder()
                        .uri(URI.create(pythonUrl + "/api/reviews/" + reviewId + "/stream"))
                        .GET()
                        .build();

                var response = httpClient.send(
                        request,
                        HttpResponse.BodyHandlers.ofInputStream()
                );

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
                log.error("SSE relay failed: reviewId={}", reviewId, e);
                emitter.completeWithError(e);
            }
        });

        emitter.onCompletion(() -> log.info("SSE completed: reviewId={}", reviewId));
        emitter.onTimeout(() -> log.warn("SSE timeout: reviewId={}", reviewId));
        emitter.onError(e -> log.error("SSE error: reviewId={}", reviewId, e));

        return emitter;
    }
}
