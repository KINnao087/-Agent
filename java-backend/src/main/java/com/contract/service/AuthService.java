package com.contract.service;

import com.contract.dto.AuthResponse;
import com.contract.dto.LoginRequest;
import com.contract.dto.RegisterRequest;
import com.contract.entity.User;
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
            throw new RuntimeException("该邮箱已被注册");
        }
        if (userRepository.existsByUsername(request.username())) {
            throw new RuntimeException("该用户名已被使用");
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
                .orElseThrow(() -> new RuntimeException("邮箱或密码错误"));

        if (!passwordEncoder.matches(request.password(), user.getPasswordHash())) {
            throw new RuntimeException("邮箱或密码错误");
        }

        String token = jwtTokenProvider.generateToken(user.getId(), user.getUsername());
        return new AuthResponse(token, user.getId(), user.getUsername(), user.getEmail());
    }

    public AuthResponse getCurrentUser(Long userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new RuntimeException("用户不存在"));
        return new AuthResponse(null, user.getId(), user.getUsername(), user.getEmail());
    }
}
