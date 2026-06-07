from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import Profile


SEED_PROFILES = [
    {
        'username': 'anjali', 'email': 'anjali@demo.com', 'password': 'demo1234',
        'full_name': 'Anjali Thapa', 'age': 26, 'gender': 'F',
        'location': 'Kathmandu, Nepal',
        'bio': 'Creative soul with a passion for art and storytelling. Love exploring hidden cafes and mountain trails.',
        'religion': 'Hindu', 'education': 'MBA Graduate', 'occupation': 'Creative Director',
        'work_preference': 'Private', 'lifestyle_tags': ['Vegetarian', 'Yoga Enthusiast', 'Avid Reader'],
        'photo_url': 'https://lh3.googleusercontent.com/aida-public/AB6AXuC-fZ55paWwu5UVxXItCduTLLUIm3DF1_aSXQLHg0lTyOa4VbxD_TCdC--sYIGqX88YTklSM02g-T3L2flLImWfsdB2P4YsbxdznwevWcaPkFbYkrI-HgqZ83bx_B9K8TqAV_BTokS0ik7qsJE5dWi8RLU8gybo2tLUYKpn3Emdjh-KZk4ioOUlQ-ney_ZTkLKh2IMktQZl1-fPJKfhsdoayYOU2VoNtl95jVmhKycCU65gMkVM7JdjCQnBRv9fC71PUIMTDR7vn3Y',
    },
    {
        'username': 'priya', 'email': 'priya@demo.com', 'password': 'demo1234',
        'full_name': 'Priya Sharma', 'age': 25, 'gender': 'F',
        'location': 'Pokhara, Nepal',
        'bio': 'Doctor by profession, dancer by heart. Looking for someone who appreciates both science and art.',
        'religion': 'Hindu', 'education': 'MBBS, TU Teaching Hospital', 'occupation': 'Doctor',
        'work_preference': 'Government', 'lifestyle_tags': ['Non-Smoker', 'Classical Dance', 'Cooking'],
        'photo_url': 'https://lh3.googleusercontent.com/aida-public/AB6AXuD78Y9AV_cFd8Au7pMtL4lmCBn__b9aJADXX6egbQXIOI5G9er0QKfam5QlFV05_6mjmba9BnmxB9WN4y7UUPxwdBU75QaXkKgQAkzRP0XiEZB-ImuAkoSdZk-9V-bYDqzOjMhvyT3anGm2-h63qyW7jsk4zXU04srN0wNsJ65nYgllvp3laDOGjSg9RQyx1FZ0KjHUZRVwzxKWRlrIWoyhnDrn_ZVSECMo3JONFlX69g4tWI7KaQfA4jEFB4ZS4SFuWCfOplrpPCU',
    },
    {
        'username': 'ananya', 'email': 'ananya@demo.com', 'password': 'demo1234',
        'full_name': 'Ananya Sharma', 'age': 27, 'gender': 'F',
        'location': 'Lalitpur, Nepal',
        'bio': 'Kathak dancer for 12 years. Technology meets tradition in my world. Looking for my soulmate.',
        'religion': 'Hindu', 'education': 'B.Tech in CS, Tribhuvan University', 'occupation': 'Software Engineer',
        'work_preference': 'Private', 'lifestyle_tags': ['Classical Dance', 'Tech Enthusiast', 'Travel'],
        'photo_url': 'https://lh3.googleusercontent.com/aida-public/AB6AXuAcPom9HhzmqluyNAjlvBEtsc_9XzOWAnGwDX8ebL5Eg_ADV4h80n1HIKgCuQ-8672mkHEsdh_AFutFkEDFmVrw2uwWGg_TcrC4261NYyfcngqdxk545DnqOF8WH3px5qByFpSwlS2E3HTnHM-U675BZyzBYUQ7SxEB1cUFJpYRGyI3CHg_Dsgr3wwsRuEomIFWUPI_Ta71wlrmEJmqagOdpjGEcsp8MliLnWBCT6J_7chSyNFt-lT-wy1708zhRJbspbWSTasz7uM',
    },
    {
        'username': 'shreya', 'email': 'shreya@demo.com', 'password': 'demo1234',
        'full_name': 'Shreya Maharjan', 'age': 24, 'gender': 'F',
        'location': 'Bhaktapur, Nepal',
        'bio': 'Architect by day, painter by night. I believe every relationship should be designed with intention.',
        'religion': 'Buddhist', 'education': 'B.Arch, Pulchowk Campus', 'occupation': 'Junior Architect',
        'work_preference': 'Private', 'lifestyle_tags': ['Art', 'Hiking', 'Photography', 'Vegetarian'],
        'photo_url': 'https://lh3.googleusercontent.com/aida-public/AB6AXuAu4_PUoXyqaGB1B5eYhASEk6P8MhlWtmKBVemUO3tOUxSYqUxk9uZtlS8mlwSbiKsOqAe74jgVgVqV3OUJN2BoECDSXR-nTrL9rpd0QYgSgb--4F0idM1Aa3M5rWwH3rH8TSzzvLmx-0o3Ge3KUy46_GgkLsIoxvbOUIttUCymzUk3ltvbQantm7jXDMKRM8JiVsuZ0IF6muDVAk3tdhTI240VVEuMhsRug11ydGLCc_fBswYxGeLSI5V-u7y3vlXvlEKTHZ8DcgA',
    },
    {
        'username': 'rahul', 'email': 'rahul@demo.com', 'password': 'demo1234',
        'full_name': 'Rahul Khadka', 'age': 29, 'gender': 'M',
        'location': 'Kathmandu, Nepal',
        'bio': 'Civil engineer building bridges and connections. Value-driven and family-oriented.',
        'religion': 'Hindu', 'education': 'B.E. Civil, IOE Pulchowk', 'occupation': 'Civil Engineer',
        'work_preference': 'Government', 'lifestyle_tags': ['Non-Smoker', 'Sports', 'Reading', 'Philanthropy'],
        'photo_url': 'https://lh3.googleusercontent.com/aida-public/AB6AXuBqhEWvA5og-Q_15LVl9q5gZFigb3ux0-WZmuTyeb8-SG3zI4yI1LPRnNeHw7CLz-4M89Opa6DhPviS_YtYW7qfFOkPabdnxm287xspECTBLa4tKxSmn9BFSABVxfG2Xkux495TArRcnrwJATLBN9kqGL9-cUenl-hg66m4F6d3g9CJd975578XdJT_oVn1RAO_0SDEzn9YwInUV0maAvyk3SGVcaoX-KOd9N1UTVJwyH8n3nq7Wuf7wOHTQPv1_cFMFs5W2_XIESk',
    },
    {
        'username': 'aaryan', 'email': 'aaryan@demo.com', 'password': 'demo1234',
        'full_name': 'Aaryan Pradhan', 'age': 28, 'gender': 'M',
        'location': 'Kathmandu, Nepal',
        'bio': 'A blend of traditional values and modern outlook. Mountain treks and complex algorithms.',
        'religion': 'Hindu', 'education': 'MBA in Strategy, IIM Bangalore', 'occupation': 'Senior Product Manager at TechFlow',
        'work_preference': 'Private', 'lifestyle_tags': ['Vegetarian', 'Non-Smoker', 'Yoga Enthusiast', 'Avid Traveler'],
        'photo_url': 'https://lh3.googleusercontent.com/aida-public/AB6AXuDJ5CfzZD40EiFWL85wbtXme4BpEL3b5RhfMvYJqojoN70oXYRV3cEjbVYUEovRzg5DZ9fRA2cW0Y7C14clzrjHfOqfpScujnpqCrxwxSXozQkIHZkCFArksNeRNmT16c3moGMSEbiG3B6DVAo1-d19ee2jFIQjedJzVO8sdM9u116Cvg_WyCejpbTlwSNus1CCH73yd196LFvpTJTCR4Yyvz2GyWgGR99Jawnucbexqb0ODJhOou-RDC_QFAU59LqJB-NR9L-ryKc',
    },
    {
        'username': 'sita', 'email': 'sita@demo.com', 'password': 'demo1234',
        'full_name': 'Sita Basnet', 'age': 25, 'gender': 'F',
        'location': 'Biratnagar, Nepal',
        'bio': 'Teacher who believes education changes everything. Passionate about reading and gardening.',
        'religion': 'Hindu', 'education': 'M.Ed, TU', 'occupation': 'High School Teacher',
        'work_preference': 'Government', 'lifestyle_tags': ['Reading', 'Gardening', 'Cooking', 'Volunteering'],
        'photo_url': 'https://lh3.googleusercontent.com/aida-public/AB6AXuARCkM5vrhnAYk7EjVNhTgux_K8Nr127teTp8Umm6WuB9fvXjMXvS0jm9rOQGfW77b8_XC8At3u74ZWaymZsOF5fj9iyHh8I04OsBoDM19m8lVcp33_E58rZX_uGp0H4Vbd3mn-VCk3wvNSSTOoWplLBY9ZXHC1FbliMbpg9-JjHXZ1SY4R6ntcznoXPQaxQWC9h9Jutixx2VFKwymHT_fE3SoSDpNki1A9fu1UiapST7ILj769iJVLQLYobvFX2IokushsqVjU2ys',
    },
    {
        'username': 'bikash', 'email': 'bikash@demo.com', 'password': 'demo1234',
        'full_name': 'Bikash Rai', 'age': 30, 'gender': 'M',
        'location': 'Pokhara, Nepal',
        'bio': 'Adventure tour guide and environmental activist. Home is where the mountains are.',
        'religion': 'Buddhist', 'education': 'BBS, Pokhara University', 'occupation': 'Tour Guide & Entrepreneur',
        'work_preference': 'Business', 'lifestyle_tags': ['Mountaineering', 'Photography', 'Cooking', 'Classic Rock'],
        'photo_url': 'https://lh3.googleusercontent.com/aida-public/AB6AXuBxTUmkhOUwF19uhq6-1Ga49JTUHNGjQwSq3zj54f9gbnCXkoHYCCJ7Irr_-ClcQjHLJw1wfnqlI4RGA9ENXENufq_3Eh6bz8JTB5qEGBB9rupmATxqRgpK4eC4__Jgf_QsI3ozGqqpbDE2XxbIpSFueRi5shUFhN44v6Fa3SEqBrgm6aUzuii1sPfa27g7XT4IDjDWvuJAAw1zbQ4pQd3zflmvuObCTqyS5DTODsghSXnjBlbtwyGjntPs2jJ17mxIOci-XNBbkJM',
    },
]


class Command(BaseCommand):
    help = 'Seed the database with demo profiles'

    def handle(self, *args, **options):
        self.stdout.write('Seeding database...')

        for data in SEED_PROFILES:
            username = data.pop('username')
            email = data.pop('email')
            password = data.pop('password')

            if User.objects.filter(username=username).exists():
                self.stdout.write(f'  Skipping {username} (already exists)')
                continue

            user = User.objects.create_user(username=username, email=email, password=password)
            profile = user.profile
            for key, value in data.items():
                setattr(profile, key, value)
            profile.is_verified = True
            profile.is_onboarded = True
            profile.save()
            self.stdout.write(f'  Created: {profile.full_name}')

        # Create a demo user for login
        if not User.objects.filter(username='demo').exists():
            user = User.objects.create_user(username='demo', email='demo@swayamvar.com', password='demo1234')
            p = user.profile
            p.full_name = 'Aarav Sharma'
            p.age = 28
            p.gender = 'M'
            p.location = 'Kathmandu, Nepal'
            p.bio = 'A blend of traditional values and modern outlook. I find joy in mountain treks and complex algorithms.'
            p.religion = 'Hindu'
            p.education = 'MBA in Strategy, IIM Bangalore'
            p.occupation = 'Senior Product Manager at TechFlow'
            p.work_preference = 'Private'
            p.lifestyle_tags = ['Vegetarian', 'Non-Smoker', 'Yoga Enthusiast', 'Avid Traveler']
            p.photo_url = 'https://lh3.googleusercontent.com/aida-public/AB6AXuDJ5CfzZD40EiFWL85wbtXme4BpEL3b5RhfMvYJqojoN70oXYRV3cEjbVYUEovRzg5DZ9fRA2cW0Y7C14clzrjHfOqfpScujnpqCrxwxSXozQkIHZkCFArksNeRNmT16c3moGMSEbiG3B6DVAo1-d19ee2jFIQjedJzVO8sdM9u116Cvg_WyCejpbTlwSNus1CCH73yd196LFvpTJTCR4Yyvz2GyWgGR99Jawnucbexqb0ODJhOou-RDC_QFAU59LqJB-NR9L-ryKc'
            p.is_verified = True
            p.is_onboarded = True
            p.pref_values = 'Looking for someone who is family-oriented, career-driven, and enjoys outdoor activities.'
            p.save()
            self.stdout.write(f'  Created demo user: demo / demo1234')

        # Create admin superuser
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@swayamvar.com', 'admin1234')
            self.stdout.write(f'  Created admin: admin / admin1234')

        self.stdout.write(self.style.SUCCESS('Done! Demo login: demo / demo1234'))
