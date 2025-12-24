from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum, F, DecimalField, Case, When
from django.db.models.functions import TruncDate
from decimal import Decimal
from .models import Transaction, SubDealerProfile

class DailyReportView(APIView):
    """
    Returns daily profit/loss and volume per SubDealer.
    """
    def get(self, request):
        # In a real app, date range filtering would be here via request.GET
        
        # Group by Date and SubDealer
        report = Transaction.objects.filter(status=Transaction.Status.APPROVED).annotate(
            date=TruncDate('created_at')
        ).values('date', 'sub_dealer__user__username').annotate(
            total_deposits=Sum(
                # Only sum DEPOSITS
                Case(
                    When(transaction_type=Transaction.TransactionType.DEPOSIT, then=F('amount')),
                    default=0,
                    output_field=DecimalField()
                )
            ),
             total_withdrawals=Sum(
                # Only sum WITHDRAWALS
                Case(
                    When(transaction_type=Transaction.TransactionType.WITHDRAW, then=F('amount')),
                    default=0,
                    output_field=DecimalField()
                )
            )
        ).order_by('-date')

        # Formatting data
        data = []
        for entry in report:
            dealer_username = entry['sub_dealer__user__username']
            deposits = entry['total_deposits'] or Decimal(0)
            withdrawals = entry['total_withdrawals'] or Decimal(0)
            
            # Need to fetch commission rate to calculate profit. 
            # (Optimized approach would be including rate in values() if possible or separate query)
            # For simplicity, assuming current rate (historic rate tracking needs a separate model).
            dealer = SubDealerProfile.objects.get(user__username=dealer_username)
            commission_rate = dealer.commission_rate
            
            # Profit = Deposits * CommissionRate
            gross_profit = deposits * (commission_rate / Decimal(100))
            
            data.append({
                "date": entry['date'],
                "dealer": dealer_username,
                "volume_in": deposits,
                "volume_out": withdrawals,
                "gross_profit": round(gross_profit, 2)
            })

        return Response(data)
