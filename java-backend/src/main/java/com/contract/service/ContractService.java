package com.contract.service;

import com.contract.dto.ContractResponse;
import com.contract.dto.ContractUploadRequest;
import com.contract.entity.Contract;
import com.contract.entity.User;
import com.contract.repository.ContractRepository;
import com.contract.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

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
                .orElseThrow(() -> new RuntimeException("用户不存在"));

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
        Contract contract = contractRepository.findById(contractId)
                .orElseThrow(() -> new RuntimeException("合同不存在"));
        if (!contract.getUser().getId().equals(userId)) {
            throw new RuntimeException("无权访问");
        }
        return ContractResponse.from(contract);
    }

    /**
     * 发起审核：调 Python 创建 review，更新本地状态，返回 reviewId。
     */
    public String startReview(Long userId, Long contractId,
                               String attachmentsPath, String invoicePath,
                               String platformBasicInfo) {
        Contract contract = contractRepository.findById(contractId)
                .orElseThrow(() -> new RuntimeException("合同不存在"));
        if (!contract.getUser().getId().equals(userId)) {
            throw new RuntimeException("无权访问");
        }

        // 调 Python 创建审核任务
        var payload = new java.util.HashMap<String, Object>();
        payload.put("contract_path", contract.getFilePath());
        payload.put("attachments_path", attachmentsPath != null ? attachmentsPath : "");
        payload.put("invoice_path", invoicePath != null ? invoicePath : "");
        payload.put("platform_basic_info", platformBasicInfo != null ? platformBasicInfo : "");
        String reviewId = pythonClient.startReview(payload);

        // 更新本地记录
        contract.setReviewId(reviewId);
        contract.setStatus(Contract.ReviewStatus.reviewing);
        contractRepository.save(contract);

        return reviewId;
    }

    /**
     * 返回审核 SSE 流。
     */
    public SseEmitter streamReview(Long userId, Long contractId) {
        Contract contract = contractRepository.findById(contractId)
                .orElseThrow(() -> new RuntimeException("合同不存在"));
        if (!contract.getUser().getId().equals(userId)) {
            throw new RuntimeException("无权访问");
        }
        if (contract.getReviewId() == null) {
            throw new RuntimeException("尚未发起审核");
        }
        return pythonClient.streamReview(contract.getReviewId());
    }

    public Map<String, Object> getReport(Long userId, Long contractId) {
        Contract contract = contractRepository.findById(contractId)
                .orElseThrow(() -> new RuntimeException("合同不存在"));
        if (!contract.getUser().getId().equals(userId)) {
            throw new RuntimeException("无权访问");
        }
        if (contract.getReviewId() == null) {
            throw new RuntimeException("尚未发起审核");
        }
        return pythonClient.getReviewReport(contract.getReviewId());
    }

    public String getReportMarkdown(Long userId, Long contractId) {
        Contract contract = contractRepository.findById(contractId)
                .orElseThrow(() -> new RuntimeException("合同不存在"));
        if (!contract.getUser().getId().equals(userId)) {
            throw new RuntimeException("无权访问");
        }
        if (contract.getReviewId() == null) {
            throw new RuntimeException("尚未发起审核");
        }
        return pythonClient.getReviewMarkdown(contract.getReviewId());
    }

    public void cancelReview(Long userId, Long contractId) {
        Contract contract = contractRepository.findById(contractId)
                .orElseThrow(() -> new RuntimeException("合同不存在"));
        if (!contract.getUser().getId().equals(userId)) {
            throw new RuntimeException("无权访问");
        }
        if (contract.getReviewId() != null) {
            pythonClient.cancelReview(contract.getReviewId());
        }
        contract.setStatus(Contract.ReviewStatus.failed);
        contractRepository.save(contract);
    }
}
