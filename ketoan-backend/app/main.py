from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import auth, sellers, customers, vouchers, attachments, sales_invoices, export, settings as settings_api, reports, scans, agent

app = FastAPI(
    title="Hệ thống quản lý kế toán nội bộ",
    description="Backend cho phiếu chi, người bán, khách hàng, hoá đơn bán ra.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(sellers.router)
app.include_router(customers.router)
app.include_router(vouchers.router)
app.include_router(attachments.router)
app.include_router(sales_invoices.router)
app.include_router(export.router)
app.include_router(settings_api.router)
app.include_router(reports.router)
app.include_router(scans.router)
app.include_router(agent.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
