import type { VoucherStatus } from "../api/types";
import { VOUCHER_STATUS_LABEL } from "../api/types";

export function StatusSeal({ status }: { status: VoucherStatus }) {
  return <span className={`status-seal status-seal--${status}`}>{VOUCHER_STATUS_LABEL[status]}</span>;
}
