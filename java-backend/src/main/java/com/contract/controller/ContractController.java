package com.contract.controller;

import com.contract.dto.ContractResponse;
import com.contract.dto.ContractUploadRequest;
import com.contract.dto.StartReviewRequest;
import com.contract.dto.UpdateContractStatusRequest;
import com.contract.exception.BadRequestException;
import com.contract.exception.NotFoundException;
import com.contract.service.ContractService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.InputStreamResource;
import org.springframework.core.io.Resource;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

@RestController
@RequestMapping("/api/contracts")
@RequiredArgsConstructor
public class ContractController {

    private static final Set<String> ALLOWED_EXTENSIONS = Set.of("pdf", "png", "jpg", "jpeg");
    private static final Set<String> ALLOWED_CONTENT_TYPES = Set.of(
            "application/pdf",
            "image/png",
            "image/jpeg"
    );

    private final ContractService contractService;

    @PostMapping
    public ResponseEntity<ContractResponse> create(
            Authentication auth,
            @RequestParam("file") MultipartFile file,
            @RequestParam("title") String title
    ) throws IOException {
        Long userId = Long.parseLong(auth.getName());
        validateUploadFile(file);
        if (title == null || title.isBlank()) {
            throw new BadRequestException("TITLE_REQUIRED", "Title is required");
        }

        Path uploadDir = Path.of(System.getProperty("user.dir"), "uploads", "contracts");
        Files.createDirectories(uploadDir);

        String fileName = System.currentTimeMillis() + "_" + file.getOriginalFilename();
        Path savePath = uploadDir.resolve(fileName);
        file.transferTo(savePath.toFile());

        ContractUploadRequest request = new ContractUploadRequest(
                title,
                savePath.toString(),
                null,
                null
        );
        return ResponseEntity.ok(contractService.createContract(userId, request));
    }

    @GetMapping
    public ResponseEntity<List<ContractResponse>> list(Authentication auth) {
        Long userId = Long.parseLong(auth.getName());
        return ResponseEntity.ok(contractService.listContracts(userId));
    }

    @GetMapping("/{id}")
    public ResponseEntity<ContractResponse> get(Authentication auth, @PathVariable Long id) {
        Long userId = Long.parseLong(auth.getName());
        return ResponseEntity.ok(contractService.getContract(userId, id));
    }

    @PostMapping("/{id}/review")
    public ResponseEntity<Map<String, Object>> startReview(
            Authentication auth,
            @PathVariable Long id,
            @RequestBody(required = false) StartReviewRequest body
    ) {
        Long userId = Long.parseLong(auth.getName());
        StartReviewRequest request = body == null
                ? new StartReviewRequest(null, null, null)
                : body;

        String reviewId = contractService.startReview(
                userId,
                id,
                request.attachmentsPath(),
                request.invoicePath(),
                request.platformBasicInfo()
        );
        return ResponseEntity.ok(Map.of("reviewId", reviewId, "status", "started"));
    }

    @GetMapping("/{id}/review/stream")
    public SseEmitter streamReview(Authentication auth, @PathVariable Long id) {
        Long userId = Long.parseLong(auth.getName());
        return contractService.streamReview(userId, id);
    }

    @GetMapping("/{id}/report")
    public ResponseEntity<Map<String, Object>> report(Authentication auth, @PathVariable Long id) {
        Long userId = Long.parseLong(auth.getName());
        return ResponseEntity.ok(contractService.getReport(userId, id));
    }

    @GetMapping("/{id}/report/markdown")
    public ResponseEntity<String> reportMarkdown(Authentication auth, @PathVariable Long id) {
        Long userId = Long.parseLong(auth.getName());
        return ResponseEntity.ok(contractService.getReportMarkdown(userId, id));
    }

    @PatchMapping("/{id}/status")
    public ResponseEntity<ContractResponse> updateStatus(
            Authentication auth,
            @PathVariable Long id,
            @Valid @RequestBody UpdateContractStatusRequest body
    ) {
        Long userId = Long.parseLong(auth.getName());
        return ResponseEntity.ok(contractService.updateStatus(userId, id, body.status()));
    }

    @DeleteMapping("/{id}/review")
    public ResponseEntity<Map<String, String>> cancel(Authentication auth, @PathVariable Long id) {
        Long userId = Long.parseLong(auth.getName());
        contractService.cancelReview(userId, id);
        return ResponseEntity.ok(Map.of("status", "cancelled"));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Map<String, String>> delete(Authentication auth, @PathVariable Long id) {
        Long userId = Long.parseLong(auth.getName());
        contractService.deleteContract(userId, id);
        return ResponseEntity.ok(Map.of("status", "deleted"));
    }

    @GetMapping("/{id}/file")
    public ResponseEntity<Resource> getFile(Authentication auth, @PathVariable Long id) throws IOException {
        Long userId = Long.parseLong(auth.getName());
        ContractResponse contract = contractService.getContract(userId, id);
        Path filePath = Path.of(contract.filePath());

        if (!Files.exists(filePath)) {
            throw new NotFoundException("CONTRACT_FILE_NOT_FOUND", "Contract file does not exist");
        }

        String fileName = filePath.getFileName().toString();
        String extension = "";
        int dotIndex = fileName.lastIndexOf('.');
        if (dotIndex >= 0) {
            extension = fileName.substring(dotIndex + 1).toLowerCase(Locale.ROOT);
        }

        MediaType mediaType = switch (extension) {
            case "png" -> MediaType.IMAGE_PNG;
            case "jpg", "jpeg" -> MediaType.IMAGE_JPEG;
            case "pdf" -> MediaType.APPLICATION_PDF;
            default -> MediaType.APPLICATION_OCTET_STREAM;
        };

        Resource resource = new InputStreamResource(Files.newInputStream(filePath));
        return ResponseEntity.ok()
                .contentType(mediaType)
                .header("Content-Disposition", "inline; filename=\"" + fileName + "\"")
                .body(resource);
    }

    private void validateUploadFile(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new BadRequestException("FILE_REQUIRED", "Please choose a file");
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
            throw new BadRequestException(
                    "UNSUPPORTED_FILE_TYPE",
                    "Only PNG, JPG, and PDF files are supported",
                    Map.of("contentType", contentType == null ? "" : contentType)
            );
        }
    }
}
