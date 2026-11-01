import { network } from "hardhat";
import { getAddress, isAddress } from "viem";

async function main() {
  const contractAddress = process.env.BLOCKCHAIN_CONTRACT_ADDRESS;
  const reporterInput = process.env.BLOCKCHAIN_REPORTER_ADDRESS;

  if (!contractAddress || !isAddress(contractAddress)) {
    throw new Error(
      "BLOCKCHAIN_CONTRACT_ADDRESS must be a valid deployed contract address.",
    );
  }
  if (!reporterInput || !isAddress(reporterInput)) {
    throw new Error(
      "BLOCKCHAIN_REPORTER_ADDRESS must be the API signer's public address.",
    );
  }

  const { viem } = await network.create();
  const [owner] = await viem.getWalletClients();
  if (!owner) {
    throw new Error("No owner account is configured for the selected network.");
  }

  const contract = await viem.getContractAt(
    "TransactionAlerts",
    getAddress(contractAddress),
  );
  const hash = await contract.write.setReporter(
    [getAddress(reporterInput), true],
    { account: owner.account },
  );
  const receipt = await (await viem.getPublicClient()).waitForTransactionReceipt({
    hash,
  });
  if (receipt.status !== "success") {
    throw new Error("Reporter authorization transaction failed.");
  }

  console.log(`Authorized reporter ${getAddress(reporterInput)}.`);
  console.log(`Transaction hash: ${hash}`);
}

main().catch((error: unknown) => {
  console.error(error);
  process.exitCode = 1;
});
