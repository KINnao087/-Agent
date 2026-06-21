package com.contract.exception;

import org.springframework.http.HttpStatus;

import java.util.Map;

public class UnauthorizedException extends AppException {

    public UnauthorizedException(String code, String message) {
        super(HttpStatus.UNAUTHORIZED, code, message);
    }

    public UnauthorizedException(String code, String message, Map<String, Object> details) {
        super(HttpStatus.UNAUTHORIZED, code, message, details);
    }
}
