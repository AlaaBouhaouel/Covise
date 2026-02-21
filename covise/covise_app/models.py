from django.db import models

class WaitlistEntry(models.Model):
    full_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=30)
    email = models.EmailField()
    country = models.CharField(max_length=100, blank=True)
    non_gcc_business = models.BooleanField(default=False)
    custom_country = models.CharField(max_length=100, blank=True)
    linkedin = models.URLField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.email})"
