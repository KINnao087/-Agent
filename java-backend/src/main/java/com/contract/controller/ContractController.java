package com.contract.controller;

import com.contract.dto.ContractResponse;
import com.contract.dto.ContractUploadRequest;
import com.contract.service.ContractService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import org.springframework.core.io.InputStreamResource;
import org.springframework.core.io.Resource;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Locale;
import java.util.List;
import java.util.Map;
import java.util.Set;

@RestController
@RequestMapping("/api/contracts")
@RequiredArgsConstructor
public class ContractController {

    private final ContractService contractService;
    private static final Set<String> ALLOWED_EXTENSIONS = Set.of("pdf", "png", "jpg", "jpeg");
    private static final Set<String> ALLOWED_CONTENT_TYPES = Set.of(
            "application/pdf",
            "image/png",
            "image/jpeg"
    );

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
        validateUploadFile(file);

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

    private void validateUploadFile(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Please choose a file");
        }

        String originalFilename = file.getOriginalFilename();
        String extension = "";
        if (originalFilename != null) {
            int dotIndex = originalFilename.lastIndexOf('.');
            if (dotIndex >= 0 && dotIndex < originalFilename.length() - 1) {
                extension = originalFilename.substring(dotIndex + 1).toLowerCase(Locale.ROOT);
            }
        }

        String contentType = file.getContentType();
        if (!ALLOWED_EXTENSIONS.contains(extension)
                || contentType == null
                || !ALLOWED_CONTENT_TYPES.contains(contentType)) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "Only PNG, JPG, and PDF files are supported"
            );
        }
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

    /**
     * 更新合同审核状态（前端推进流转：pending → reviewing → pending_review → completed）。
     */
    @PatchMapping("/{id}/status")
    public ResponseEntity<ContractResponse> updateStatus(
            Authentication auth,
            @PathVariable Long id,
            @RequestBody Map<String, String> body) {
        Long userId = Long.parseLong(auth.getName());
        String status = body.get("status");
        return ResponseEntity.ok(contractService.updateStatus(userId, id, status));
    }

    @DeleteMapping("/{id}/review")
    public ResponseEntity<Map<String, String>> cancel(
            Authentication auth, @PathVariable Long id) {
        Long userId = Long.parseLong(auth.getName());
        contractService.cancelReview(userId, id);
        return ResponseEntity.ok(Map.of("status", "cancelled"));
    }

    /**
     * 删除合同（同时删除本地文件和远程审核）。
     */
    @DeleteMapping("/{id}")
    public ResponseEntity<Map<String, String>> delete(
            Authentication auth, @PathVariable Long id) {
        Long userId = Long.parseLong(auth.getName());
        contractService.deleteContract(userId, id);
        return ResponseEntity.ok(Map.of("status", "deleted"));
    }

    /**
     * 获取合同文件用于前端预览（图片 / PDF）。
     */
    @GetMapping("/{id}/file")
    public ResponseEntity<Resource> getFile(
            Authentication auth, @PathVariable Long id) throws IOException {
        Long userId = Long.parseLong(auth.getName());
        ContractResponse contract = contractService.getContract(userId, id);
        Path filePath = Path.of(contract.filePath());

        if (!Files.exists(filePath)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "文件不存在");
        }

        String fileName = filePath.getFileName().toString();
        String extension = "";
        int dotIndex = fileName.lastIndexOf('.');
        if (dotIndex >= 0) {
            extension = fileName.substring(dotIndex + 1).toLowerCase();
        }

        MediaType mediaType = switch (extension) {
            case "png"  -> MediaType.IMAGE_PNG;
            case "jpg", "jpeg" -> MediaType.IMAGE_JPEG;
            case "pdf"  -> MediaType.APPLICATION_PDF;
            default     -> MediaType.APPLICATION_OCTET_STREAM;
        };

        Resource resource = new InputStreamResource(Files.newInputStream(filePath));
        return ResponseEntity.ok()
                .contentType(mediaType)
                .header("Content-Disposition", "inline; filename=\"" + fileName + "\"")
                .body(resource);
    }
}
