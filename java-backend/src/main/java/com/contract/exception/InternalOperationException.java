package com.contract.exception;

import org.springframework.http.HttpStatus;

import java.util.Map;

public class InternalOperationException extends AppException {

    public InternalOperationException(String code, String message) {
        super(HttpStatus.INTERNAL_SERVER_ERROR, code, message);
    }

    public InternalOperationException(String code, String message, Map<String, Object> details) {
        super(HttpStatus.INTERNAL_SERVER_ERROR, code, message, details);
    }
}
