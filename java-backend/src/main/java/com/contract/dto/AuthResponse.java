package com.contract.dto;

public record AuthResponse(
        String token,
        Long userId,
        String username,
        String email) {}
