from django.urls import path
from .views import create_hmsmi,post_test_results

urlpatterns = [
    path('hmsmi/create/', create_hmsmi, name='create_hmsmi'),
    path('post-test-results/<path:bill_number>/', post_test_results, name='post-test-results'),
]
