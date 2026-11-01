import { network } from "hardhat";

async function main() {
  const { viem } = await network.create();

  const contrat = await viem.deployContract("TransactionAlerts");

  console.log("Contrat TransactionAlerts déployé avec succès !");
  console.log("Adresse du contrat :", contrat.address);
  console.log("CONTRACT_ADDRESS=" + contrat.address);
}

main().catch((erreur) => {
  console.error(erreur);
  process.exitCode = 1;
});
