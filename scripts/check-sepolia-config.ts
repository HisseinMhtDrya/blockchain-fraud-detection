import { network } from "hardhat";
import { formatEther } from "viem";

const SEPOLIA_CHAIN_ID = 11155111;

async function main(): Promise<void> {
  const { viem } = await network.create();
  const publicClient = await viem.getPublicClient();

  let chainId: number;
  try {
    chainId = await publicClient.getChainId();
  } catch {
    throw new Error(
      "Impossible de joindre le RPC Sepolia. Vérifiez SEPOLIA_RPC_URL et l'accès réseau.",
    );
  }

  if (chainId !== SEPOLIA_CHAIN_ID) {
    throw new Error(
      `Mauvais réseau RPC : chain ID ${chainId}, attendu ${SEPOLIA_CHAIN_ID} (Sepolia).`,
    );
  }

  let accounts;
  try {
    accounts = await viem.getWalletClients();
  } catch {
    throw new Error(
      "Impossible de charger le compte de déploiement. Vérifiez SEPOLIA_PRIVATE_KEY.",
    );
  }

  const deployer = accounts[0];
  if (!deployer) {
    throw new Error(
      "Aucun compte de déploiement disponible. Configurez SEPOLIA_PRIVATE_KEY.",
    );
  }

  let balance: bigint;
  try {
    balance = await publicClient.getBalance({
      address: deployer.account.address,
    });
  } catch {
    throw new Error(
      "Le RPC Sepolia répond, mais le solde du compte n'a pas pu être lu.",
    );
  }

  console.log("Configuration Sepolia valide (vérification en lecture seule).");
  console.log(`Chain ID : ${chainId}`);
  console.log(`Adresse publique du déployeur : ${deployer.account.address}`);
  console.log(`Solde Sepolia : ${formatEther(balance)} ETH`);
  console.log("Aucune transaction n'a été envoyée.");
}

main().catch((error: unknown) => {
  const message =
    error instanceof Error
      ? error.message
      : "Erreur inattendue pendant la vérification Sepolia.";
  console.error(`Échec de la vérification Sepolia : ${message}`);
  process.exitCode = 1;
});
