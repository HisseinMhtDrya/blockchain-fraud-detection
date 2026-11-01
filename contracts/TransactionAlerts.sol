// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

/// @title TransactionAlerts
/// @notice Enregistre les alertes issues du modèle ML.
contract TransactionAlerts {
    address public owner;
    mapping(address => bool) public reporters;

    bool private _locked;

    uint256 public constant MAX_TRANSACTION_ID_LENGTH = 128;

    struct Alert {
        string transactionId;
        uint8 riskScore;
        bool illicit;
        uint256 timestamp;
        address reporter;
    }

    Alert[] private alerts;

    event AlertRecorded(
        uint256 indexed alertId,
        string transactionId,
        uint8 riskScore,
        bool illicit,
        uint256 timestamp,
        address reporter
    );

    error InvalidRiskScore();
    error EmptyTransactionId();
    error TransactionIdTooLong();
    error UnauthorizedReporter();
    error InvalidOwner();
    error AlreadyOwner();

    event OwnershipTransferred(
        address indexed previousOwner,
        address indexed newOwner
    );
    event ReporterUpdated(address indexed reporter, bool authorized);

    constructor() {
        owner = msg.sender;
        reporters[msg.sender] = true;
        emit OwnershipTransferred(address(0), msg.sender);
        emit ReporterUpdated(msg.sender, true);
    }

    modifier onlyOwner() {
        if (msg.sender != owner) {
            revert UnauthorizedReporter();
        }
        _;
    }

    modifier onlyReporter() {
        if (!reporters[msg.sender]) {
            revert UnauthorizedReporter();
        }
        _;
    }

    modifier nonReentrant() {
        require(!_locked, "Reentrant call");
        _locked = true;
        _;
        _locked = false;
    }

    function setReporter(address reporter, bool authorized) external onlyOwner {
        if (reporter == address(0)) {
            revert InvalidOwner();
        }
        reporters[reporter] = authorized;
        emit ReporterUpdated(reporter, authorized);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) {
            revert InvalidOwner();
        }
        if (newOwner == owner) {
            revert AlreadyOwner();
        }

        address previousOwner = owner;
        owner = newOwner;
        reporters[previousOwner] = false;
        reporters[newOwner] = true;
        emit ReporterUpdated(previousOwner, false);
        emit ReporterUpdated(newOwner, true);
        emit OwnershipTransferred(previousOwner, newOwner);
    }

    function recordAlert(
        string calldata transactionId,
        uint8 riskScore,
        bool illicit
    ) external onlyReporter nonReentrant returns (uint256 alertId) {
        if (bytes(transactionId).length == 0) {
            revert EmptyTransactionId();
        }
        if (bytes(transactionId).length > MAX_TRANSACTION_ID_LENGTH) {
            revert TransactionIdTooLong();
        }

        if (riskScore > 100) {
            revert InvalidRiskScore();
        }

        alertId = alerts.length;

        alerts.push(
            Alert({
                transactionId: transactionId,
                riskScore: riskScore,
                illicit: illicit,
                timestamp: block.timestamp,
                reporter: msg.sender
            })
        );

        emit AlertRecorded(
            alertId,
            transactionId,
            riskScore,
            illicit,
            block.timestamp,
            msg.sender
        );
    }

    function getAlert(uint256 alertId)
        external
        view
        returns (Alert memory)
    {
        if (alertId >= alerts.length) {
            revert("Alerte inexistante");
        }
        return alerts[alertId];
    }

    function getAlertCount() external view returns (uint256) {
        return alerts.length;
    }
}
