package com.contract.service;

import com.contract.exception.BadRequestException;
import com.contract.exception.ExternalServiceException;
import com.contract.exception.NotFoundException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
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

    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {};

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

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(pythonUrl + "/api/reviews"))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(json, StandardCharsets.UTF_8))
                    .build();

            HttpResponse<String> response = sendText(request);
            ensureSuccess(
                    response,
                    "PYTHON_REVIEW_START_INVALID",
                    "Python review request is invalid",
                    "REVIEW_NOT_FOUND",
                    "Review resource does not exist",
                    "PYTHON_REVIEW_START_FAILED",
                    "Failed to start review in Python service"
            );

            Map<String, Object> result = MAPPER.readValue(response.body(), Map.class);
            Object reviewId = result.get("review_id");
            if (!(reviewId instanceof String reviewIdValue) || reviewIdValue.isBlank()) {
                throw new ExternalServiceException(
                        "PYTHON_REVIEW_START_INVALID_RESPONSE",
                        "Python service did not return a valid review id"
                );
            }
            return reviewIdValue;
        } catch (BadRequestException | NotFoundException | ExternalServiceException exception) {
            throw exception;
        } catch (Exception exception) {
            log.error("Failed to call Python start review", exception);
            throw new ExternalServiceException(
                    "PYTHON_REVIEW_START_FAILED",
                    "Failed to start review in Python service"
            );
        }
    }

    public Map<String, Object> getReviewStatus(String reviewId) {
        try {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(pythonUrl + "/api/reviews/" + reviewId + "/status"))
                    .GET()
                    .build();

            HttpResponse<String> response = sendText(request);
            ensureSuccess(
                    response,
                    "PYTHON_REVIEW_STATUS_INVALID",
                    "Review status request is invalid",
                    "REVIEW_NOT_FOUND",
                    "Review does not exist",
                    "PYTHON_REVIEW_STATUS_FAILED",
                    "Failed to fetch review status from Python service"
            );
            return MAPPER.readValue(response.body(), MAP_TYPE);
        } catch (BadRequestException | NotFoundException | ExternalServiceException exception) {
            throw exception;
        } catch (Exception exception) {
            log.error("Failed to fetch review status", exception);
            throw new ExternalServiceException(
                    "PYTHON_REVIEW_STATUS_FAILED",
                    "Failed to fetch review status from Python service"
            );
        }
    }

    public Map<String, Object> getReviewReport(String reviewId) {
        try {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(pythonUrl + "/api/reviews/" + reviewId + "/report"))
                    .GET()
                    .build();

            HttpResponse<String> response = sendText(request);
            ensureSuccess(
                    response,
                    "PYTHON_REVIEW_REPORT_INVALID",
                    "Review report request is invalid",
                    "REVIEW_NOT_FOUND",
                    "Review does not exist",
                    "PYTHON_REVIEW_REPORT_FAILED",
                    "Failed to fetch review report from Python service"
            );
            return MAPPER.readValue(response.body(), MAP_TYPE);
        } catch (BadRequestException | NotFoundException | ExternalServiceException exception) {
            throw exception;
        } catch (Exception exception) {
            log.error("Failed to fetch review report", exception);
            throw new ExternalServiceException(
                    "PYTHON_REVIEW_REPORT_FAILED",
                    "Failed to fetch review report from Python service"
            );
        }
    }

    public String getReviewMarkdown(String reviewId) {
        try {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(pythonUrl + "/api/reviews/" + reviewId + "/report/markdown"))
                    .GET()
                    .build();

            HttpResponse<String> response = sendText(request);
            ensureSuccess(
                    response,
                    "PYTHON_REVIEW_MARKDOWN_INVALID",
                    "Markdown report request is invalid",
                    "REVIEW_REPORT_NOT_READY",
                    "Markdown report has not been generated yet",
                    "PYTHON_REVIEW_MARKDOWN_FAILED",
                    "Failed to fetch markdown report from Python service"
            );
            return response.body();
        } catch (BadRequestException | NotFoundException | ExternalServiceException exception) {
            throw exception;
        } catch (Exception exception) {
            log.error("Failed to fetch markdown report", exception);
            throw new ExternalServiceException(
                    "PYTHON_REVIEW_MARKDOWN_FAILED",
                    "Failed to fetch markdown report from Python service"
            );
        }
    }

    public void cancelReview(String reviewId) {
        try {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(pythonUrl + "/api/reviews/" + reviewId))
                    .DELETE()
                    .build();

            HttpResponse<String> response = sendText(request);
            ensureSuccess(
                    response,
                    "PYTHON_REVIEW_CANCEL_INVALID",
                    "Review cancel request is invalid",
                    "REVIEW_NOT_FOUND",
                    "Review does not exist",
                    "PYTHON_REVIEW_CANCEL_FAILED",
                    "Failed to cancel review in Python service"
            );
        } catch (BadRequestException | NotFoundException | ExternalServiceException exception) {
            throw exception;
        } catch (Exception exception) {
            log.error("Failed to cancel review", exception);
            throw new ExternalServiceException(
                    "PYTHON_REVIEW_CANCEL_FAILED",
                    "Failed to cancel review in Python service"
            );
        }
    }

    public SseEmitter streamReview(String reviewId) {
        SseEmitter emitter = new SseEmitter(30 * 60 * 1000L);

        sseExecutor.execute(() -> {
            try {
                HttpRequest request = HttpRequest.newBuilder()
                        .uri(URI.create(pythonUrl + "/api/reviews/" + reviewId + "/stream"))
                        .GET()
                        .build();

                HttpResponse<java.io.InputStream> response = httpClient.send(
                        request,
                        HttpResponse.BodyHandlers.ofInputStream()
                );

                if (response.statusCode() != 200) {
                    throw new ExternalServiceException(
                            "PYTHON_REVIEW_STREAM_FAILED",
                            "Failed to connect review stream from Python service"
                    );
                }

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
            } catch (Exception exception) {
                log.error("SSE relay failed: reviewId={}", reviewId, exception);
                emitter.completeWithError(exception);
            }
        });

        emitter.onCompletion(() -> log.info("SSE completed: reviewId={}", reviewId));
        emitter.onTimeout(() -> log.warn("SSE timeout: reviewId={}", reviewId));
        emitter.onError(error -> log.error("SSE error: reviewId={}", reviewId, error));

        return emitter;
    }

    private HttpResponse<String> sendText(HttpRequest request) throws Exception {
        return httpClient.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
    }

    private void ensureSuccess(
            HttpResponse<String> response,
            String badRequestCode,
            String badRequestMessage,
            String notFoundCode,
            String notFoundMessage,
            String downstreamCode,
            String downstreamMessage
    ) {
        int statusCode = response.statusCode();
        if (statusCode >= 200 && statusCode < 300) {
            return;
        }

        String message = extractDownstreamMessage(response.body(), downstreamMessage);
        Map<String, Object> details = Map.of(
                "downstreamStatus", statusCode,
                "downstreamMessage", message
        );

        if (statusCode == 400 || statusCode == 422) {
            throw new BadRequestException(badRequestCode, message == null ? badRequestMessage : message, details);
        }
        if (statusCode == 404) {
            throw new NotFoundException(notFoundCode, message == null ? notFoundMessage : message, details);
        }

        throw new ExternalServiceException(
                downstreamCode,
                message == null ? downstreamMessage : message,
                details
        );
    }

    private String extractDownstreamMessage(String body, String fallback) {
        if (body == null || body.isBlank()) {
            return fallback;
        }

        try {
            Map<String, Object> payload = MAPPER.readValue(body, MAP_TYPE);
            Object message = payload.get("message");
            if (message instanceof String messageValue && !messageValue.isBlank()) {
                return messageValue;
            }
            Object detail = payload.get("detail");
            if (detail instanceof String detailValue && !detailValue.isBlank()) {
                return detailValue;
            }
        } catch (Exception ignored) {
            // Fall back to raw body below.
        }

        return body.isBlank() ? fallback : body;
    }
}
