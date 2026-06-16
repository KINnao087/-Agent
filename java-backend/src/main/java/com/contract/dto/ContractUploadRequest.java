package com.contract.dto;

import jakarta.validation.constraints.NotBlank;

public record ContractUploadRequest(
        @NotBlank String title,
        String filePath,
        String attachmentsPath,
        String invoicePath) {}
