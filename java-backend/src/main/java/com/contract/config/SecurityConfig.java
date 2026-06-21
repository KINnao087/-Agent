package com.contract.config;

import com.contract.dto.ApiErrorResponse;
import com.contract.security.JwtAuthenticationFilter;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.DispatcherType;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

import java.io.IOException;
import java.time.OffsetDateTime;
import java.util.Map;

@Configuration
@Slf4j
@EnableWebSecurity
@RequiredArgsConstructor
public class SecurityConfig {

    private final JwtAuthenticationFilter jwtAuthenticationFilter;
    private final ObjectMapper objectMapper;

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
                .cors(cors -> {})
                .csrf(csrf -> csrf.disable())
                .sessionManagement(session -> session
                        .sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .exceptionHandling(exception -> exception
                        .authenticationEntryPoint((request, response, authException) -> {
                            String code = resolveAuthenticationCode(request);
                            String message = resolveAuthenticationMessage(request);
                            log.warn(
                                    "401 entry point: method={}, uri={}, query={}, code={}, message={}",
                                    request.getMethod(),
                                    request.getRequestURI(),
                                    request.getQueryString(),
                                    code,
                                    message
                            );
                            writeErrorResponse(
                                    response,
                                    HttpStatus.UNAUTHORIZED,
                                    code,
                                    message,
                                    request.getRequestURI(),
                                    Map.of()
                            );
                        })
                        .accessDeniedHandler((request, response, accessDeniedException) -> {
                            log.warn(
                                    "403 access denied: method={}, uri={}, message={}",
                                    request.getMethod(),
                                    request.getRequestURI(),
                                    accessDeniedException.getMessage()
                            );
                            writeErrorResponse(
                                    response,
                                    HttpStatus.FORBIDDEN,
                                    "AUTHORIZATION_FORBIDDEN",
                                    "You do not have permission to access this resource",
                                    request.getRequestURI(),
                                    Map.of()
                            );
                        }))
                .authorizeHttpRequests(auth -> auth
                        .dispatcherTypeMatchers(DispatcherType.ERROR, DispatcherType.ASYNC).permitAll()
                        .requestMatchers("/api/auth/register", "/api/auth/login").permitAll()
                        .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
                        .anyRequest().authenticated())
                .addFilterBefore(jwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    public AuthenticationManager authenticationManager(AuthenticationConfiguration config) throws Exception {
        return config.getAuthenticationManager();
    }

    private String resolveAuthenticationCode(HttpServletRequest request) {
        Object code = request.getAttribute(JwtAuthenticationFilter.AUTH_ERROR_CODE_ATTR);
        if (code instanceof String codeValue && !codeValue.isBlank()) {
            return codeValue;
        }
        return "AUTHENTICATION_REQUIRED";
    }

    private String resolveAuthenticationMessage(HttpServletRequest request) {
        Object message = request.getAttribute(JwtAuthenticationFilter.AUTH_ERROR_MESSAGE_ATTR);
        if (message instanceof String messageValue && !messageValue.isBlank()) {
            return messageValue;
        }
        return "Authentication is required";
    }

    private void writeErrorResponse(
            HttpServletResponse response,
            HttpStatus status,
            String code,
            String message,
            String path,
            Map<String, Object> details
    ) throws IOException {
        response.setStatus(status.value());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding("UTF-8");

        ApiErrorResponse body = new ApiErrorResponse(
                status.value(),
                code,
                message,
                path,
                OffsetDateTime.now(),
                details
        );
        objectMapper.writeValue(response.getWriter(), body);
    }
}
