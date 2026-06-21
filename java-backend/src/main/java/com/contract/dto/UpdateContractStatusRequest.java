package com.contract.dto;

import jakarta.validation.constraints.NotBlank;

public record UpdateContractStatusRequest(@NotBlank String status) {}
