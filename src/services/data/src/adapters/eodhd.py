"""EODHD API adapter for fundamentals data (earnings, financials, economic indicators).

EODHD provides comprehensive fundamental data including:
- Company financials (balance sheet, income statement, cash flow)
- Earnings data and estimates
- Economic indicators (GDP, inflation, interest rates)
- Insider transactions and institutional holdings

API Documentation: https://eodhistoricaldata.com/financial-apis/
Rate Limits: 100,000 requests/day for paid plans, 20 requests/day for free
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
import os
from .base import APIAdapter, DataFetchError


class EODHDAdapter(APIAdapter):
    """EODHD API adapter for fundamental data."""
    
    name = "eodhd"
    base_url = "https://eodhistoricaldata.com/api"
    rate_limit_per_sec = 1.0  # Conservative rate limiting (1 req/sec = 86,400/day)
    
    def __init__(self, http=None, *, timeout: Optional[float] = None):
        super().__init__(http, timeout=timeout)
        # API key from environment variable
        self.api_key = os.getenv("EODHD_API_KEY")
        if not self.api_key:
            raise DataFetchError(self.name, "EODHD_API_KEY environment variable not set")
    
    def _build_request(self, **kwargs) -> tuple[str, Dict[str, Any], Optional[Dict[str, str]]]:
        """Build EODHD API request.
        
        Supported data types:
        - fundamentals: Company fundamental data
        - earnings: Earnings data and estimates  
        - economic: Economic indicators
        - insider_transactions: Insider trading data
        """
        data_type = kwargs.get("data_type", "fundamentals")
        symbol = kwargs.get("symbol", "AAPL.US")
        
        # Base parameters for all requests
        params: Dict[str, Any] = {
            "api_token": self.api_key,
            "fmt": "json"
        }
        
        if data_type == "fundamentals":
            path = f"/fundamentals/{symbol}"
            # Optional filters for fundamental data
            if kwargs.get("filter"):
                params["filter"] = kwargs["filter"]
                
        elif data_type == "earnings":
            path = f"/calendar/earnings"
            params["symbols"] = symbol
            # Date range for earnings
            if kwargs.get("from_date"):
                params["from"] = kwargs["from_date"]
            if kwargs.get("to_date"):
                params["to"] = kwargs["to_date"]
                
        elif data_type == "economic":
            path = "/economic-events"
            # Economic indicators don't require symbol
            params.pop("symbols", None)
            if kwargs.get("country"):
                params["country"] = kwargs["country"]
            if kwargs.get("from_date"):
                params["from"] = kwargs["from_date"]
            if kwargs.get("to_date"):
                params["to"] = kwargs["to_date"]
                
        elif data_type == "insider_transactions":
            path = f"/insider-transactions"
            params["code"] = symbol
            if kwargs.get("limit"):
                params["limit"] = kwargs["limit"]
                
        else:
            raise DataFetchError(self.name, f"Unsupported data_type: {data_type}")
        
        headers = {
            "User-Agent": "FKS-Trading/1.0"
        }
        
        return self.base_url + path, params, headers
    
    def _normalize(self, raw: Any, *, request_kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize EODHD API response."""
        data_type = request_kwargs.get("data_type", "fundamentals")
        
        if not isinstance(raw, (dict, list)):
            raise DataFetchError(self.name, f"Unexpected payload type: {type(raw)}")
        
        try:
            if data_type == "fundamentals":
                return self._normalize_fundamentals(raw, request_kwargs)
            elif data_type == "earnings":
                return self._normalize_earnings(raw, request_kwargs)
            elif data_type == "economic":
                return self._normalize_economic(raw, request_kwargs)
            elif data_type == "insider_transactions":
                return self._normalize_insider_transactions(raw, request_kwargs)
            else:
                # Generic normalization for unknown types
                return {
                    "provider": self.name,
                    "data_type": data_type,
                    "data": raw,
                    "request": request_kwargs,
                    "timestamp": datetime.utcnow().isoformat()
                }
        except Exception as e:
            raise DataFetchError(self.name, f"Normalization error: {str(e)}")
    
    def _normalize_fundamentals(self, raw: Dict[str, Any], request_kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize fundamental data response."""
        symbol = request_kwargs.get("symbol", "")
        
        # Extract key financial metrics
        financials = raw.get("Financials", {})
        balance_sheet = financials.get("Balance_Sheet", {})
        income_statement = financials.get("Income_Statement", {})
        cash_flow = financials.get("Cash_Flow", {})
        
        # Get latest annual data (yearly data is more reliable)
        latest_annual = {}
        if balance_sheet.get("yearly"):
            latest_bs = list(balance_sheet["yearly"].values())[0] if balance_sheet["yearly"] else {}
            latest_annual.update(latest_bs)
        
        if income_statement.get("yearly"):
            latest_is = list(income_statement["yearly"].values())[0] if income_statement["yearly"] else {}
            latest_annual.update(latest_is)
            
        if cash_flow.get("yearly"):
            latest_cf = list(cash_flow["yearly"].values())[0] if cash_flow["yearly"] else {}
            latest_annual.update(latest_cf)
        
        # Extract key ratios and metrics
        highlights = raw.get("Highlights", {})
        valuation = raw.get("Valuation", {})
        
        normalized_data = {
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "general": raw.get("General", {}),
            "highlights": highlights,
            "valuation": valuation,
            "latest_financials": latest_annual,
            "raw_financials": financials
        }
        
        return {
            "provider": self.name,
            "data_type": "fundamentals",
            "data": [normalized_data],
            "request": request_kwargs
        }
    
    def _normalize_earnings(self, raw: List[Dict[str, Any]], request_kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize earnings calendar response."""
        normalized_data = []
        
        for earning in raw:
            normalized_data.append({
                "symbol": earning.get("code"),
                "company_name": earning.get("name"),
                "earnings_date": earning.get("report_date"),
                "period_ending": earning.get("period_ending"),
                "estimate": earning.get("estimate"),
                "actual": earning.get("actual"),
                "difference": earning.get("difference"),
                "surprise_percent": earning.get("surprise_percent"),
                "timestamp": datetime.utcnow().isoformat()
            })
        
        return {
            "provider": self.name,
            "data_type": "earnings",
            "data": normalized_data,
            "request": request_kwargs
        }
    
    def _normalize_economic(self, raw: List[Dict[str, Any]], request_kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize economic indicators response."""
        normalized_data = []
        
        for event in raw:
            normalized_data.append({
                "country": event.get("country"),
                "event_name": event.get("event"),
                "date": event.get("date"),
                "time": event.get("time"),
                "currency": event.get("currency"),
                "importance": event.get("importance"),
                "actual": event.get("actual"),
                "estimate": event.get("estimate"),
                "previous": event.get("previous"),
                "change_percent": event.get("change_percent"),
                "timestamp": datetime.utcnow().isoformat()
            })
        
        return {
            "provider": self.name,
            "data_type": "economic",
            "data": normalized_data,
            "request": request_kwargs
        }
    
    def _normalize_insider_transactions(self, raw: List[Dict[str, Any]], request_kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize insider transactions response."""
        normalized_data = []
        
        for transaction in raw:
            normalized_data.append({
                "symbol": transaction.get("code"),
                "insider_name": transaction.get("fullName"),
                "position": transaction.get("position"),
                "transaction_date": transaction.get("transactionDate"),
                "transaction_type": transaction.get("transactionType"),
                "shares": transaction.get("shares"),
                "price": transaction.get("price"),
                "value": transaction.get("value"),
                "timestamp": datetime.utcnow().isoformat()
            })
        
        return {
            "provider": self.name,
            "data_type": "insider_transactions", 
            "data": normalized_data,
            "request": request_kwargs
        }


__all__ = ["EODHDAdapter"]