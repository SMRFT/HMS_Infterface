from django.urls import path
from .views import create_hmsmi,get_test_results

urlpatterns = [
    path('hmsmi/create/', create_hmsmi, name='create_hmsmi'),
    path('testresults/', get_test_results, name='get_test_results'),
]
