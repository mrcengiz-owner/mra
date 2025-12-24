from django.core.management.base import BaseCommand
from accounts.models import SubDealerProfile
import logging

class Command(BaseCommand):
    help = 'Refreshes Net Balance and System Status for all SubDealers.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting Dealer Status Refresh...")
        dealers = SubDealerProfile.objects.all()
        count = 0
        fixed = 0

        for dealer in dealers:
            old_balance = dealer.current_net_balance
            old_active = dealer.is_active_by_system
            
            # Recalculate
            new_balance = dealer.recalculate_balance()
            
            # Check if status changed
            if dealer.is_active_by_system != old_active:
                self.stdout.write(self.style.WARNING(f"FIXED: {dealer.user.username} -> Status changed to {dealer.is_active_by_system} (Balance: {new_balance})"))
                fixed += 1
            elif old_balance != new_balance:
                self.stdout.write(f"UPDATED: {dealer.user.username} -> Balance {old_balance} -> {new_balance}")
            
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully refreshed {count} dealers. Fixed {fixed} issues."))
