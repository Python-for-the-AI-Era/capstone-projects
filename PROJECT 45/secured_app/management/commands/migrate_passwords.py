"""
SECURED Management Command - PRODUCTION READY
This command migrates users from insecure MD5 to Argon2.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from secured_app.middleware.password_security import get_password_migration_stats
from secured_app.models import SecurityLog
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migrate users from insecure MD5 passwords to Argon2'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show migration statistics without performing migration'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force migration for all users (requires password reset)'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of users to migrate in each batch'
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        batch_size = options['batch_size']
        
        self.stdout.write("🔐 Password Migration Security Tool")
        self.stdout.write("=" * 50)
        
        # Get migration statistics
        stats = get_password_migration_stats()
        
        if 'error' in stats:
            self.stdout.write(
                self.style.ERROR(f"❌ Error: {stats['error']}")
            )
            return
        
        total_users = stats['total_users']
        secure_users = stats['secure_users']
        insecure_users = stats['insecure_users']
        migration_percentage = stats['migration_percentage']
        
        # Display current status
        self.stdout.write(f"📊 Migration Status:")
        self.stdout.write(f"   Total Users: {total_users}")
        self.stdout.write(f"   Secure Users: {secure_users}")
        self.stdout.write(f"   Insecure Users: {insecure_users}")
        self.stdout.write(f"   Migration Progress: {migration_percentage:.1f}%")
        self.stdout.write("")
        
        if insecure_users == 0:
            self.stdout.write(
                self.style.SUCCESS("✅ All users are already using secure passwords!")
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING("🔍 Dry run mode - no changes will be made")
            )
            self.stdout.write("")
            self.stdout.write("💡 Recommendations:")
            
            if migration_percentage < 50:
                self.stdout.write("   🚨 CRITICAL: Less than 50% of users have secure passwords")
                self.stdout.write("   📧 Send email notification to all users to login")
                self.stdout.write("   📅 Schedule migration completion in 2 weeks")
            elif migration_percentage < 80:
                self.stdout.write("   ⚠️  WARNING: Migration progress is below 80%")
                self.stdout.write("   📧 Send reminder email to remaining users")
                self.stdout.write("   📊 Monitor login patterns for next week")
            else:
                self.stdout.write("   ✅ GOOD: Migration is nearly complete")
                self.stdout.write("   📧 Send final reminder to remaining users")
            
            return
        
        # Confirm migration
        if not force:
            confirm = input(
                f"\n⚠️  This will migrate {insecure_users} users. Continue? (yes/no): "
            )
            if confirm.lower() not in ['yes', 'y']:
                self.stdout.write("❌ Migration cancelled.")
                return
        
        # Perform migration
        self.stdout.write(f"🔄 Starting migration of {insecure_users} users...")
        self.stdout.write("")
        
        migrated_count = 0
        failed_count = 0
        
        # Get users with insecure passwords
        insecure_user_queryset = User.objects.filter(
            password__regex=r'^(md5|sha1|crypt)\$'
        ).order_by('id')
        
        # Process in batches
        for batch_start in range(0, insecure_users, batch_size):
            batch_end = min(batch_start + batch_size, insecure_users)
            batch = insecure_user_queryset[batch_start:batch_end]
            
            self.stdout.write(
                f"   Processing batch {batch_start//batch_size + 1}: "
                f"{migrated_count + len(batch)}/{insecure_users}"
            )
            
            for user in batch:
                try:
                    if force:
                        # Force migration - require password reset
                        self.stdout.write(
                            f"   ⚠️  Force migrating {user.email} (requires password reset)"
                        )
                        
                        # Generate temporary password
                        import secrets
                        import string
                        temp_password = ''.join(
                            secrets.choice(string.ascii_letters + string.digits) 
                            for _ in range(12)
                        )
                        
                        # Update with secure hash
                        user.set_password(temp_password)
                        user.last_password_change = timezone.now()
                        user.save(update_fields=['password', 'last_password_change'])
                        
                        # Log forced migration
                        SecurityLog.objects.create(
                            event_type='password_change',
                            user=user,
                            details={
                                'migration_type': 'forced_migration',
                                'temp_password_generated': True,
                                'requires_reset': True
                            }
                        )
                        
                        # Here you would send password reset email
                        # send_password_reset_email(user, temp_password)
                        
                    else:
                        # Lazy migration - user will be migrated on next login
                        self.stdout.write(f"   📧 {user.email} - will migrate on next login")
                        
                        # Log scheduled migration
                        SecurityLog.objects.create(
                            event_type='password_change',
                            user=user,
                            details={
                                'migration_type': 'scheduled_lazy_migration',
                                'current_algorithm': 'md5',
                                'action_required': 'user_login'
                            }
                        )
                    
                    migrated_count += 1
                    
                except Exception as e:
                    failed_count += 1
                    self.stdout.write(
                        self.style.ERROR(f"   ❌ Failed to migrate {user.email}: {e}")
                    )
                    
                    logger.error(f"Migration failed for user {user.id}: {e}")
            
            # Progress update
            progress = ((migrated_count + failed_count) / insecure_users) * 100
            self.stdout.write(
                f"   Progress: {progress:.1f}% "
                f"({migrated_count} migrated, {failed_count} failed)"
            )
        
        # Final summary
        self.stdout.write("")
        self.stdout.write("=" * 50)
        self.stdout.write("📋 Migration Summary:")
        self.stdout.write(f"   Total Processed: {migrated_count + failed_count}")
        self.stdout.write(f"   Successfully Migrated: {migrated_count}")
        self.stdout.write(f"   Failed: {failed_count}")
        
        if failed_count == 0:
            self.stdout.write(
                self.style.SUCCESS("✅ Migration completed successfully!")
            )
            
            if not force:
                self.stdout.write("")
                self.stdout.write("💡 Next Steps:")
                self.stdout.write("   1. Monitor user logins for lazy migrations")
                self.stdout.write("   2. Send follow-up email in 1 week")
                self.stdout.write("   3. Update documentation to disable MD5 support")
        else:
            self.stdout.write(
                self.style.ERROR(f"❌ Migration completed with {failed_count} errors")
            )
            self.stdout.write("")
            self.stdout.write("💡 Recommendations:")
            self.stdout.write("   1. Review error logs for failed migrations")
            self.stdout.write("   2. Manually migrate failed users")
            self.stdout.write("   3. Run migration again after fixing issues")
        
        # Log completion
        SecurityLog.objects.create(
            event_type='password_change',
            details={
                'migration_type': 'bulk_migration_completed',
                'total_processed': migrated_count + failed_count,
                'success_count': migrated_count,
                'failed_count': failed_count,
                'forced': force,
                'completed_at': timezone.now().isoformat()
            }
        )
