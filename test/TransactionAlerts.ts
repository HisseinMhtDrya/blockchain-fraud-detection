import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { network } from "hardhat";

describe("TransactionAlerts", function () {
  it("enregistre une alerte et retourne son nombre", async function () {
    const { viem } = await network.create();

    const contrat = await viem.deployContract("TransactionAlerts");

    const hash = await contrat.write.recordAlert(["tx-test-001", 95, true]);

    const nombre = await contrat.read.getAlertCount();
    assert.equal(nombre, 1n);

    const alerte = await contrat.read.getAlert([0n]);
    assert.equal(alerte.transactionId, "tx-test-001");
    assert.equal(alerte.riskScore, 95);
    assert.equal(alerte.illicit, true);
  });

  it("restreint les alertes aux reporters autorisés", async function () {
    const { viem } = await network.create();
    const [reporter, outsider] = await viem.getWalletClients();
    const contrat = await viem.deployContract("TransactionAlerts");

    await viem.assertions.revertWithCustomError(
      contrat.write.recordAlert(["tx-unauthorized", 80, true], {
        account: outsider.account,
      }),
      contrat,
      "UnauthorizedReporter",
    );

    await viem.assertions.emitWithArgs(
      contrat.write.setReporter([reporter.account.address, true]),
      contrat,
      "ReporterUpdated",
      [reporter.account.address, true],
    );
    await contrat.write.recordAlert(["tx-authorized", 80, true], {
      account: reporter.account,
    });

    assert.equal(await contrat.read.getAlertCount(), 1n);
  });

  it("refuse les mises à jour de reporters non autorisées et les entrées invalides", async function () {
    const { viem } = await network.create();
    const [owner, outsider] = await viem.getWalletClients();
    const contrat = await viem.deployContract("TransactionAlerts");

    await viem.assertions.revertWithCustomError(
      contrat.write.setReporter([outsider.account.address, true], {
        account: outsider.account,
      }),
      contrat,
      "UnauthorizedReporter",
    );
    await viem.assertions.revertWithCustomError(
      contrat.write.setReporter(["0x0000000000000000000000000000000000000000", true]),
      contrat,
      "InvalidOwner",
    );
    await viem.assertions.revertWithCustomError(
      contrat.write.recordAlert(["", 80, true], { account: owner.account }),
      contrat,
      "EmptyTransactionId",
    );
    await viem.assertions.revertWithCustomError(
      contrat.write.recordAlert(["x".repeat(129), 80, true], {
        account: owner.account,
      }),
      contrat,
      "TransactionIdTooLong",
    );
    await viem.assertions.revertWithCustomError(
      contrat.write.recordAlert(["tx-too-risky", 101, true], {
        account: owner.account,
      }),
      contrat,
      "InvalidRiskScore",
    );
  });

  it("transfère la propriété et révoque le rôle reporter de l'ancien propriétaire", async function () {
    const { viem } = await network.create();
    const [owner, nextOwner] = await viem.getWalletClients();
    const contrat = await viem.deployContract("TransactionAlerts");

    await viem.assertions.emitWithArgs(
      contrat.write.transferOwnership([nextOwner.account.address]),
      contrat,
      "OwnershipTransferred",
      [owner.account.address, nextOwner.account.address],
    );

    assert.equal((await contrat.read.owner()).toLowerCase(), nextOwner.account.address.toLowerCase());
    assert.equal(
      await contrat.read.reporters([owner.account.address]),
      false,
    );
    assert.equal(
      await contrat.read.reporters([nextOwner.account.address]),
      true,
    );
    await viem.assertions.revertWithCustomError(
      contrat.write.recordAlert(["tx-former-owner", 50, false], {
        account: owner.account,
      }),
      contrat,
      "UnauthorizedReporter",
    );
  });
});
