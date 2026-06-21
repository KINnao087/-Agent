package com.contract.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.WebAuthenticationDetailsSource;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.Collections;

@Slf4j
@Component
@RequiredArgsConstructor
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    public static final String AUTH_ERROR_CODE_ATTR = "auth_error_code";
    public static final String AUTH_ERROR_MESSAGE_ATTR = "auth_error_message";

    private final JwtTokenProvider jwtTokenProvider;
    private final UserDetailsServiceImpl userDetailsService;

    @Override
    protected boolean shouldNotFilterAsyncDispatch() {
        // SSE requests finish through async dispatch. Re-run JWT extraction there
        // so the resumed request is not treated as anonymous.
        return false;
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain
    ) throws ServletException, IOException {

        String token = extractToken(request);

        log.debug(
                "JWT filter: method={}, uri={}, hasToken={}",
                request.getMethod(),
                request.getRequestURI(),
                StringUtils.hasText(token)
        );

        boolean valid = false;
        if (StringUtils.hasText(token)) {
            valid = jwtTokenProvider.validateToken(token);
            log.debug("JWT filter: token validation result={}", valid);
            if (!valid) {
                request.setAttribute(
                        AUTH_ERROR_CODE_ATTR,
                        jwtTokenProvider.isTokenExpired(token)
                                ? "AUTHENTICATION_TOKEN_EXPIRED"
                                : "AUTHENTICATION_INVALID_TOKEN"
                );
                request.setAttribute(
                        AUTH_ERROR_MESSAGE_ATTR,
                        jwtTokenProvider.isTokenExpired(token)
                                ? "Authentication token has expired"
                                : "Authentication token is invalid"
                );
                log.warn(
                        "JWT filter: token INVALID, prefix={}",
                        token.substring(0, Math.min(20, token.length()))
                );
            }
        }

        if (StringUtils.hasText(token) && valid) {
            try {
                Long userId = jwtTokenProvider.getUserIdFromToken(token);
                log.debug("JWT filter: token valid, userId={}", userId);
                var userDetails = userDetailsService.loadUserById(userId);
                log.debug("JWT filter: userDetails loaded, username={}", userDetails.getUsername());

                var authentication = new UsernamePasswordAuthenticationToken(
                        userDetails,
                        null,
                        userDetails != null ? userDetails.getAuthorities() : Collections.emptyList()
                );
                authentication.setDetails(
                        new WebAuthenticationDetailsSource().buildDetails(request)
                );

                SecurityContextHolder.getContext().setAuthentication(authentication);
            } catch (RuntimeException exception) {
                SecurityContextHolder.clearContext();
                request.setAttribute(AUTH_ERROR_CODE_ATTR, "AUTHENTICATION_USER_NOT_FOUND");
                request.setAttribute(
                        AUTH_ERROR_MESSAGE_ATTR,
                        "Authenticated user no longer exists"
                );
                log.warn("JWT filter: failed to load user from token", exception);
            }
        }

        filterChain.doFilter(request, response);
    }

    private String extractToken(HttpServletRequest request) {
        String bearerToken = request.getHeader("Authorization");
        if (StringUtils.hasText(bearerToken) && bearerToken.startsWith("Bearer ")) {
            return bearerToken.substring(7);
        }

        // EventSource cannot set custom headers, so SSE uses query token fallback.
        String queryToken = request.getParameter("token");
        if (StringUtils.hasText(queryToken)) {
            return queryToken;
        }
        return null;
    }
}
