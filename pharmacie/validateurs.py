from django.core.validators import RegexValidator

valider_telephone = RegexValidator(
    regex=r"^\+?[0-9 ]{7,20}$",
    message="Numéro invalide. Exemples : 034 12 345 67 ou +261 34 12 345 67.",
)