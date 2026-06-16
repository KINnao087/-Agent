package com.contract.controller;

import com.contract.dto.ContractResponse;
import com.contract.dto.ContractUploadRequest;
import com.contract.service.ContractService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/contracts")
@RequiredArgsConstructor
public class ContractController {

    private final ContractService contractService;

//    @PostMapping
//    public ResponseEntity<ContractResponse> create(
//            Authentication auth,
//            @Valid @RequestBody ContractUploadRequest request) {
//        Long userId = Long.parseLong(auth.getName());
//        return ResponseEntity.ok(contractService.createContract(userId, request));
//    }
    @PostMapping
    public ResponseEntity<ContractResponse> create(
            Authentication auth,
            @RequestParam("file") MultipartFile file,
            @RequestParam("title") String title
    ) throws IOException {
        Long userId = Long.parseLong(auth.getName());

        // 把文件保存到本地服务器（绝对路径）
        Path uploadDir = Path.of(System.getProperty("user.dir"), "uploads", "contracts");
        Files.createDirectories(uploadDir);

        String fileName = System.currentTimeMillis() + "_" + file.getOriginalFilename();
        Path savePath = uploadDir.resolve(fileName);

        file.transferTo(savePath.toFile());

        ContractUploadRequest req = new ContractUploadRequest(
            title,
            savePath.toString(),
            null, null
        );
        return ResponseEntity.ok(contractService.createContract(userId, req));
    }

    @GetMapping
    public ResponseEntity<List<ContractResponse>> list(Authentication auth) {
        Long userId = Long.parseLong(auth.getName());
        return ResponseEntity.ok(contractService.listContracts(userId));
    }

    @GetMapping("/{id}")
    public ResponseEntity<ContractResponse> get(
            Authentication auth, @PathVariable Long id) {
        Long userId = Long.parseLong(auth.getName());
        return ResponseEntity.ok(contractService.getContract(userId, id));
    }

    /**
     * 发起合同审核 — 调 Python 创建任务，返回 reviewId。
     */
    @PostMapping("/{id}/review")
    public ResponseEntity<Map<String, Object>> startReview(
            Authentication auth,
            @PathVariable Long id,
            @RequestBody(required = false) Map<String, String> body) {
        Long userId = Long.parseLong(auth.getName());
        String attachmentsPath = body != null ? body.get("attachments_path") : null;
        String invoicePath = body != null ? body.get("invoice_path") : null;
        String platformInfo = body != null ? body.get("platform_basic_info") : null;
        String reviewId = contractService.startReview(userId, id, attachmentsPath, invoicePath, platformInfo);
        return ResponseEntity.ok(Map.of("reviewId", reviewId, "status", "started"));
    }

    /**
     * SSE 流式推送审核进度 — GET 方式（浏览器 EventSource 限制只能用 GET）。
     */
    @GetMapping("/{id}/review/stream")
    public SseEmitter streamReview(
            Authentication auth,
            @PathVariable Long id) {
        Long userId = Long.parseLong(auth.getName());
        return contractService.streamReview(userId, id);
    }

    @GetMapping("/{id}/report")
    public ResponseEntity<Map<String, Object>> report(
            Authentication auth, @PathVariable Long id) {
        Long userId = Long.parseLong(auth.getName());
        return ResponseEntity.ok(contractService.getReport(userId, id));
    }

    @GetMapping("/{id}/report/markdown")
    public ResponseEntity<String> reportMarkdown(
            Authentication auth, @PathVariable Long id) {
        Long userId = Long.parseLong(auth.getName());
        return ResponseEntity.ok(contractService.getReportMarkdown(userId, id));
    }

    @DeleteMapping("/{id}/review")
    public ResponseEntity<Map<String, String>> cancel(
            Authentication auth, @PathVariable Long id) {
        Long userId = Long.parseLong(auth.getName());
        contractService.cancelReview(userId, id);
        return ResponseEntity.ok(Map.of("status", "cancelled"));
    }
}
