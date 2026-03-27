"""
MKJ SUPA CUP - Initial County Data Population

This script populates the County model with all 47 Kenyan counties
and includes sample sports officer contact information.
"""

from django.core.management.base import BaseCommand
from teams.models import County


class Command(BaseCommand):
    help = 'Populate the County model with all 47 Kenyan counties'

    def handle(self, *args, **options):
        counties_data = [
            # Name, Code, Capital, Sports Officer Name, Sports Officer Email, Phone
            ("Baringo", "BAR", "Kabarnet", "John Kiplagat", "sports.baringo@gmail.com", "+254720123001"),
            ("Bomet", "BOT", "Bomet", "Mary Cherotich", "sportsoffice.bomet@gmail.com", "+254720123002"),
            ("Bungoma", "BUN", "Bungoma", "Peter Wanyonyi", "sports.bungoma@gmail.com", "+254720123003"),
            ("Busia", "BUS", "Busia", "Grace Awino", "busia.sports@gmail.com", "+254720123004"),
            ("Elgeyo-Marakwet", "EMW", "Iten", "Samuel Kiprotich", "sports.elgeyomarakwet@gmail.com", "+254720123005"),
            ("Embu", "EMB", "Embu", "Catherine Wanjiku", "embu.sports@gmail.com", "+254720123006"),
            ("Garissa", "GAR", "Garissa", "Ahmed Hassan", "garissa.sports@gmail.com", "+254720123007"),
            ("Homa Bay", "HOM", "Homa Bay", "Daniel Ochieng", "homabay.sports@gmail.com", "+254720123008"),
            ("Isiolo", "ISO", "Isiolo", "Fatuma Ali", "isiolo.sports@gmail.com", "+254720123009"),
            ("Kajiado", "KAJ", "Kajiado", "Joseph Sankale", "kajiado.sports@gmail.com", "+254720123010"),
            ("Kakamega", "KAK", "Kakamega", "Margaret Wanjala", "kakamega.sports@gmail.com", "+254720123011"),
            ("Kericho", "KER", "Kericho", "Timothy Kiprop", "kericho.sports@gmail.com", "+254720123012"),
            ("Kiambu", "KIA", "Kiambu", "Susan Wanjiru", "kiambu.sports@gmail.com", "+254720123013"),
            ("Kilifi", "KIL", "Kilifi", "Omar Salim", "kilifi.sports@gmail.com", "+254720123014"),
            ("Kirinyaga", "KIR", "Kerugoya", "Peter Mwangi", "kirinyaga.sports@gmail.com", "+254720123015"),
            ("Kisii", "KIS", "Kisii", "Grace Nyaboke", "kisii.sports@gmail.com", "+254720123016"),
            ("Kisumu", "KSM", "Kisumu", "Michael Otieno", "kisumu.sports@gmail.com", "+254720123017"),
            ("Kitui", "KIT", "Kitui", "Agnes Mutindi", "kitui.sports@gmail.com", "+254720123018"),
            ("Kwale", "KWA", "Kwale", "Hassan Mwalimu", "kwale.sports@gmail.com", "+254720123019"),
            ("Laikipia", "LAI", "Nanyuki", "David Kariuki", "laikipia.sports@gmail.com", "+254720123020"),
            ("Lamu", "LAM", "Lamu", "Amina Mohamed", "lamu.sports@gmail.com", "+254720123021"),
            ("Machakos", "MAC", "Machakos", "Francis Musyoka", "machakos.sports@gmail.com", "+254720123022"),
            ("Makueni", "MAK", "Wote", "Jane Kavuu", "makueni.sports@gmail.com", "+254720123023"),
            ("Mandera", "MAN", "Mandera", "Abdullahi Ibrahim", "mandera.sports@gmail.com", "+254720123024"),
            ("Marsabit", "MAR", "Marsabit", "Halima Galgalo", "marsabit.sports@gmail.com", "+254720123025"),
            ("Meru", "MER", "Meru", "Boniface Muthuri", "meru.sports@gmail.com", "+254720123026"),
            ("Migori", "MIG", "Migori", "Rose Awuor", "migori.sports@gmail.com", "+254720123027"),
            ("Mombasa", "MSA", "Mombasa", "Ali Rashid", "mombasa.sports@gmail.com", "+254720123028"),
            ("Murang'a", "MUR", "Murang'a", "James Githinji", "muranga.sports@gmail.com", "+254720123029"),
            ("Nairobi", "NAI", "Nairobi", "Sarah Njeri", "nairobi.sports@gmail.com", "+254720123030"),
            ("Nakuru", "NAK", "Nakuru", "Robert Kimani", "nakuru.sports@gmail.com", "+254720123031"),
            ("Nandi", "NAN", "Kapsabet", "Lydia Chebet", "nandi.sports@gmail.com", "+254720123032"),
            ("Narok", "NAR", "Narok", "Wilson Sankale", "narok.sports@gmail.com", "+254720123033"),
            ("Nyamira", "NYA", "Nyamira", "Esther Moraa", "nyamira.sports@gmail.com", "+254720123034"),
            ("Nyandarua", "NYN", "Ol Kalou", "Patrick Mwangi", "nyandarua.sports@gmail.com", "+254720123035"),
            ("Nyeri", "NYE", "Nyeri", "Ann Wambui", "nyeri.sports@gmail.com", "+254720123036"),
            ("Samburu", "SAM", "Maralal", "Jackson Lekalgitele", "samburu.sports@gmail.com", "+254720123037"),
            ("Siaya", "SIA", "Siaya", "Tom Odhiambo", "siaya.sports@gmail.com", "+254720123038"),
            ("Taita-Taveta", "TTA", "Voi", "Elizabeth Mwakio", "taitataveta.sports@gmail.com", "+254720123039"),
            ("Tana River", "TAN", "Hola", "Salim Juma", "tanariver.sports@gmail.com", "+254720123040"),
            ("Tharaka-Nithi", "THN", "Chuka", "Moses Kimathi", "tharakanithi.sports@gmail.com", "+254720123041"),
            ("Trans Nzoia", "TNZ", "Kitale", "Alice Wanjala", "transnzoia.sports@gmail.com", "+254720123042"),
            ("Turkana", "TUR", "Lodwar", "Paul Ekale", "turkana.sports@gmail.com", "+254720123043"),
            ("Uasin Gishu", "UAS", "Eldoret", "Mercy Chepkemoi", "uasingishu.sports@gmail.com", "+254720123044"),
            ("Vihiga", "VIH", "Vihiga", "Nancy Shiundu", "vihiga.sports@gmail.com", "+254720123045"),
            ("Wajir", "WAJ", "Wajir", "Amina Abdi", "wajir.sports@gmail.com", "+254720123046"),
            ("West Pokot", "WPK", "Kapenguria", "Simon Pkosing", "westpokot.sports@gmail.com", "+254720123047"),
        ]

        created_count = 0
        updated_count = 0

        for name, code, capital, officer_name, officer_email, phone in counties_data:
            county, created = County.objects.get_or_create(
                name=name,
                defaults={
                    'code': code,
                    'capital': capital,
                    'sports_officer_name': officer_name,
                    'sports_officer_email': officer_email,
                    'sports_officer_phone': phone,
                    'office_address': f"{capital} County Sports Office",
                    'is_active': True,
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f"✅ Created: {name}")
            else:
                # Update existing county with sports officer info if missing
                if not county.sports_officer_email:
                    county.code = code
                    county.capital = capital
                    county.sports_officer_name = officer_name
                    county.sports_officer_email = officer_email
                    county.sports_officer_phone = phone
                    county.office_address = f"{capital} County Sports Office"
                    county.save()
                    updated_count += 1
                    self.stdout.write(f"🔄 Updated: {name}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\n🎯 County data population complete!\n"
                f"   Created: {created_count} counties\n"
                f"   Updated: {updated_count} counties\n"
                f"   Total: {County.objects.count()} counties in database"
            )
        )