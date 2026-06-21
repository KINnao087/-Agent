package com.contract.exception;

import org.springframework.http.HttpStatus;

import java.util.Map;

public class ForbiddenException extends AppException {

    public ForbiddenException(String code, String message) {
        super(HttpStatus.FORBIDDEN, code, message);
    }

    public ForbiddenException(String code, String message, Map<String, Object> details) {
        super(HttpStatus.FORBIDDEN, code, message, details);
    }
}
