package com.contract.exception;

import org.springframework.http.HttpStatus;

import java.util.Map;

public class ConflictException extends AppException {

    public ConflictException(String code, String message) {
        super(HttpStatus.CONFLICT, code, message);
    }

    public ConflictException(String code, String message, Map<String, Object> details) {
        super(HttpStatus.CONFLICT, code, message, details);
    }
}
