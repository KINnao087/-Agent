package com.contract.service;

import com.contract.dto.ContractResponse;
import com.contract.dto.ContractUploadRequest;
import com.contract.entity.Contract;
import com.contract.entity.User;
import com.contract.exception.BadRequestException;
import com.contract.exception.ForbiddenException;
import com.contract.exception.InternalOperationException;
import com.contract.exception.NotFoundException;
import com.contract.repository.ContractRepository;
import com.contract.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class ContractService {

    private final ContractRepository contractRepository;
    private final UserRepository userRepository;
    private final PythonClientService pythonClient;

    public ContractResponse createContract(Long userId, ContractUploadRequest request) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new NotFoundException("USER_NOT_FOUND", "User does not exist"));

        Contract contract = Contract.builder()
                .user(user)
                .title(request.title())
                .filePath(request.filePath())
                .status(Contract.ReviewStatus.pending)
                .build();
        contract = contractRepository.save(contract);
        return ContractResponse.from(contract);
    }

    public List<ContractResponse> listContracts(Long userId) {
        return contractRepository.findByUserIdOrderByCreatedAtDesc(userId)
                .stream()
                .map(ContractResponse::from)
                .toList();
    }

    public ContractResponse getContract(Long userId, Long contractId) {
        return ContractResponse.from(getOwnedContract(userId, contractId));
    }

    public String startReview(
            Long userId,
            Long contractId,
            String attachmentsPath,
            String invoicePath,
            Map<String, Object> platformBasicInfo
    ) {
        Contract contract = getOwnedContract(userId, contractId);

        var payload = new java.util.HashMap<String, Object>();
        payload.put("contract_path", contract.getFilePath());
        payload.put("attachments_path", attachmentsPath != null ? attachmentsPath : "");
        payload.put("invoice_path", invoicePath != null ? invoicePath : "");
        payload.put("platform_basic_info", platformBasicInfo);

        String reviewId = pythonClient.startReview(payload);
        contract.setReviewId(reviewId);
        contract.setStatus(Contract.ReviewStatus.reviewing);
        contractRepository.save(contract);
        return reviewId;
    }

    public SseEmitter streamReview(Long userId, Long contractId) {
        Contract contract = getOwnedContract(userId, contractId);
        if (contract.getReviewId() == null) {
            throw new BadRequestException("REVIEW_NOT_STARTED", "Review has not been started");
        }
        return pythonClient.streamReview(contract.getReviewId());
    }

    public Map<String, Object> getReport(Long userId, Long contractId) {
        Contract contract = getOwnedContract(userId, contractId);
        if (contract.getReviewId() == null) {
            throw new BadRequestException("REVIEW_NOT_STARTED", "Review has not been started");
        }
        return pythonClient.getReviewReport(contract.getReviewId());
    }

    public String getReportMarkdown(Long userId, Long contractId) {
        Contract contract = getOwnedContract(userId, contractId);
        if (contract.getReviewId() == null) {
            throw new BadRequestException("REVIEW_NOT_STARTED", "Review has not been started");
        }
        return pythonClient.getReviewMarkdown(contract.getReviewId());
    }

    public ContractResponse updateStatus(Long userId, Long contractId, String newStatus) {
        Contract contract = getOwnedContract(userId, contractId);
        if (newStatus == null || newStatus.isBlank()) {
            throw new BadRequestException("STATUS_REQUIRED", "Status is required");
        }

        Contract.ReviewStatus parsedStatus;
        try {
            parsedStatus = Contract.ReviewStatus.valueOf(newStatus);
        } catch (IllegalArgumentException exception) {
            throw new BadRequestException(
                    "INVALID_CONTRACT_STATUS",
                    "Unsupported contract status",
                    Map.of("status", newStatus)
            );
        }

        contract.setStatus(parsedStatus);
        contract = contractRepository.save(contract);
        return ContractResponse.from(contract);
    }

    public void cancelReview(Long userId, Long contractId) {
        Contract contract = getOwnedContract(userId, contractId);
        if (contract.getReviewId() == null) {
            throw new BadRequestException("REVIEW_NOT_STARTED", "Review has not been started");
        }

        pythonClient.cancelReview(contract.getReviewId());
        contract.setStatus(Contract.ReviewStatus.failed);
        contractRepository.save(contract);
    }

    public void deleteContract(Long userId, Long contractId) {
        Contract contract = getOwnedContract(userId, contractId);

        if (contract.getReviewId() != null) {
            try {
                pythonClient.cancelReview(contract.getReviewId());
            } catch (NotFoundException exception) {
                log.info(
                        "Remote review already missing during delete: contractId={}, reviewId={}",
                        contractId,
                        contract.getReviewId()
                );
            }
        }

        if (contract.getFilePath() != null) {
            try {
                Files.deleteIfExists(Path.of(contract.getFilePath()));
            } catch (IOException exception) {
                throw new InternalOperationException(
                        "CONTRACT_FILE_DELETE_FAILED",
                        "Failed to delete contract file",
                        Map.of("filePath", contract.getFilePath())
                );
            }
        }

        contractRepository.delete(contract);
    }

    private Contract getOwnedContract(Long userId, Long contractId) {
        Contract contract = contractRepository.findById(contractId)
                .orElseThrow(() -> new NotFoundException("CONTRACT_NOT_FOUND", "Contract does not exist"));
        if (!contract.getUser().getId().equals(userId)) {
            throw new ForbiddenException("CONTRACT_ACCESS_DENIED", "You do not have access to this contract");
        }
        return contract;
    }
}
