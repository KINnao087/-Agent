package com.contract.dto;

import java.time.OffsetDateTime;
import java.util.Map;

public record ApiErrorResponse(
        int status,
        String code,
        String message,
        String path,
        OffsetDateTime timestamp,
        Map<String, Object> details
) {}
