package com.contract.service;

import com.contract.dto.AuthResponse;
import com.contract.dto.LoginRequest;
import com.contract.dto.RegisterRequest;
import com.contract.entity.User;
import com.contract.exception.ConflictException;
import com.contract.exception.NotFoundException;
import com.contract.exception.UnauthorizedException;
import com.contract.repository.UserRepository;
import com.contract.security.JwtTokenProvider;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider jwtTokenProvider;

    public AuthResponse register(RegisterRequest request) {
        if (userRepository.existsByEmail(request.email())) {
            throw new ConflictException("AUTH_EMAIL_IN_USE", "Email is already registered");
        }
        if (userRepository.existsByUsername(request.username())) {
            throw new ConflictException("AUTH_USERNAME_IN_USE", "Username is already in use");
        }

        User user = User.builder()
                .username(request.username())
                .email(request.email())
                .passwordHash(passwordEncoder.encode(request.password()))
                .build();
        user = userRepository.save(user);

        String token = jwtTokenProvider.generateToken(user.getId(), user.getUsername());
        return new AuthResponse(token, user.getId(), user.getUsername(), user.getEmail());
    }

    public AuthResponse login(LoginRequest request) {
        User user = userRepository.findByEmail(request.email())
                .orElseThrow(() -> new UnauthorizedException(
                        "AUTH_INVALID_CREDENTIALS",
                        "Email or password is incorrect"
                ));

        if (!passwordEncoder.matches(request.password(), user.getPasswordHash())) {
            throw new UnauthorizedException(
                    "AUTH_INVALID_CREDENTIALS",
                    "Email or password is incorrect"
            );
        }

        String token = jwtTokenProvider.generateToken(user.getId(), user.getUsername());
        return new AuthResponse(token, user.getId(), user.getUsername(), user.getEmail());
    }

    public AuthResponse getCurrentUser(Long userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new NotFoundException("USER_NOT_FOUND", "User does not exist"));
        return new AuthResponse(null, user.getId(), user.getUsername(), user.getEmail());
    }
}
