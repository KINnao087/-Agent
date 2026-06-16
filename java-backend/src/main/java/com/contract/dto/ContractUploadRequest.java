package com.contract.dto;

import jakarta.validation.constraints.NotBlank;

public record ContractUploadRequest(
        @NotBlank String title,
        String filePath,
        String attachmentsPath,  // 附件路径
        String invoicePath) {}   // 发票路径
