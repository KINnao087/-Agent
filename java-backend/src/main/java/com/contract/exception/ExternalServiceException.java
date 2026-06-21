package com.contract.exception;

import org.springframework.http.HttpStatus;

import java.util.Map;

public class ExternalServiceException extends AppException {

    public ExternalServiceException(String code, String message) {
        super(HttpStatus.BAD_GATEWAY, code, message);
    }

    public ExternalServiceException(String code, String message, Map<String, Object> details) {
        super(HttpStatus.BAD_GATEWAY, code, message, details);
    }
}
