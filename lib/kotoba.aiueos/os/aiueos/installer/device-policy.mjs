export const destructivePhrase = (device) => `ERASE ${device} FOR AIUEOS`;

export function assessInstallTarget(info, systemDisks) {
  const reasons = [];
  if (!info || typeof info.path !== "string") reasons.push("device inspection returned no canonical path");
  if (info?.type !== "disk" || info?.whole !== true) reasons.push("target is not a whole disk");
  if (info?.internal !== true) reasons.push("target is not an internal disk");
  if (info?.empty !== true) reasons.push("target is not empty (partitions or filesystem signatures exist)");
  if (info?.mounted === true) reasons.push("target or one of its children is mounted");
  if (info?.boot === true || info?.system === true) reasons.push("target is a current boot/system disk");
  if (!Array.isArray(systemDisks) || systemDisks.length === 0) reasons.push("current boot/system disk could not be identified");
  if (systemDisks?.includes(info?.path)) reasons.push("target matches a current boot/system disk");
  return { allowed: reasons.length === 0, reasons };
}

export function requireDestructiveConfirmation(device, repeatedDevice, phrase) {
  if (repeatedDevice !== device) throw new Error("--confirm-device must exactly repeat --device");
  if (phrase !== destructivePhrase(device)) throw new Error(`--destructive-phrase must exactly equal: ${destructivePhrase(device)}`);
}
