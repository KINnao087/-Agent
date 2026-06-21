package com.contract.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.Map;

public record StartReviewRequest(
        @JsonProperty("attachments_path") String attachmentsPath,
        @JsonProperty("invoice_path") String invoicePath,
        @JsonProperty("platform_basic_info") Map<String, Object> platformBasicInfo
) {}
