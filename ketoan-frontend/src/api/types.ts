export type RoleName = "giam_doc" | "ke_toan" | "thu_quy" | "nhan_vien";

export interface CurrentUser {
  id: string;
  username: string;
  full_name: string;
  role_name: RoleName;
  is_active: boolean;
}

/** Cùng hình dạng với CurrentUser, dùng khi liệt kê user KHÁC (không phải người đang đăng nhập) */
export type UserOut = CurrentUser;

export interface Seller {
  id: string;
  name: string;
  address: string | null;
  id_card_number: string | null;
  phone: string | null;
  alias_of_seller_id: string | null;
  created_at: string;
}

export interface SellerDuplicateCandidate {
  seller: Seller;
  similarity_score: number;
}

export interface Customer {
  id: string;
  company_name: string;
  tax_code: string | null;
  address: string | null;
  contact_phone: string | null;
  bank_account: string | null;
  created_at: string;
}

export type VoucherStatus = "draft" | "pending_signature" | "signed" | "archived" | "void";

export interface Voucher {
  id: string;
  so_phieu: string;
  ngay: string;
  seller_id: string;
  ly_do_chi: string;
  so_tien: string;
  so_luong: string | null;
  don_gia: string | null;
  ghi_chu_chat_luong: string | null;
  trang_thai: VoucherStatus;
  created_by: string;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export const VOUCHER_STATUS_LABEL: Record<VoucherStatus, string> = {
  draft: "Nháp",
  pending_signature: "Chờ ký",
  signed: "Đã ký",
  archived: "Lưu trữ",
  void: "Đã huỷ",
};

export type PaymentMethod = "chuyen_khoan" | "tien_mat";
export type SalesInvoiceStatus = "draft" | "issued" | "reconciled";

export interface SalesInvoice {
  id: string;
  so_hoa_don: string | null;
  ky_hieu: string | null;
  ngay: string;
  customer_id: string;
  ten_hang: string;
  so_luong: string;
  don_gia: string;
  thue_suat: string;
  tong_tien: string;
  payment_method: PaymentMethod;
  trang_thai: SalesInvoiceStatus;
  paid_at: string | null;
  created_at: string;
}

export const SALES_INVOICE_STATUS_LABEL: Record<SalesInvoiceStatus, string> = {
  draft: "Nháp",
  issued: "Đã xuất hoá đơn",
  reconciled: "Đã đối chiếu",
};

export interface CompanySettings {
  company_name: string;
  company_address: string;
  company_tax_code: string;
  company_phone: string;
}

export interface TopSeller {
  seller_id: string;
  seller_name: string;
  tong_tien: number;
  tong_so_luong: number;
  so_phieu: number;
  so_thang_phat_sinh: number;
  id_card_number: string | null;
  phone: string | null;
  address: string | null;
}

export interface DashboardSummary {
  month: number;
  year: number;
  months: number;
  tu_thang: string;
  den_thang: string;
  tong_chi_thang_nay: number;
  so_phieu_thang_nay: number;
  so_phieu_cho_duyet: number;
  so_phieu_cho_ky_qua_han: number;
  top_nguoi_ban: TopSeller[];
  cong_no_phai_thu: number;
  so_hoa_don_cho_thu: number;
}

export interface ExtractedRow {
  ten_nguoi_ban: string;
  ten_hang_hoa: string | null;
  so_luong: number;
  don_gia: number;
  tong_gia_thanh_toan: number;
  do_tin_cay_thap: boolean;
  canh_bao_phep_nhan: boolean;
  canh_bao_ten_khong_khop: boolean;
  seller_id_goi_y: string | null;
}

export interface ScanExtractResponse {
  scan_id: string;
  rows: ExtractedRow[];
}

export interface ScanConfirmResponse {
  so_phieu_da_tao: number;
  voucher_ids: string[];
}

export interface ScanImportListItem {
  id: string;
  status: "pending" | "confirmed" | "discarded";
  created_at: string;
  confirmed_at: string | null;
  so_dong_trich_xuat: number;
  so_dong_xac_nhan: number | null;
}

export interface ScanImportDetail extends ScanImportListItem {
  raw_extraction: Record<string, unknown>[] | null;
  confirmed_extraction: Record<string, unknown>[] | null;
}


export interface AgentHistoryMessage {
  role: "user" | "assistant";
  content: string;
}

/** Thẻ đề xuất phiếu chi nháp — KHÔNG phải phiếu thật, chỉ lưu khi người dùng bấm xác nhận. */
export interface AgentProposal {
  seller_id: string | null;
  seller_name: string;
  ngay: string;
  ly_do_chi: string;
  so_tien: number;
  so_luong: number | null;
  don_gia: number | null;
  warnings: string[];
}

export interface AgentChatResponse {
  reply: string;
  history: AgentHistoryMessage[];
  tool_calls_made: string[];
  proposals: AgentProposal[];
}

export interface AgentAlert {
  type: string;
  severity: "warn" | "alert";
  title: string;
  detail: string;
  link: string;
}
