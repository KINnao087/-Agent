package com.contract.dto;

import com.contract.entity.Contract;
import java.time.LocalDateTime;

public record ContractResponse(
        Long id,
        String title,
        String filePath,
        String reviewId,
        String status,
        LocalDateTime createdAt) {

    public static ContractResponse from(Contract c) {
        return new ContractResponse(
                c.getId(), c.getTitle(), c.getFilePath(),
                c.getReviewId(), c.getStatus().name(), c.getCreatedAt());
    }
}
