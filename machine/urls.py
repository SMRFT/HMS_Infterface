from django.urls import path
from .views import (
    create_hmsmi, 
    post_test_results, 
    manual_entry_page, 
    send_manual_result, 
    search_machine_records, 
    fetch_test_data,
    get_queue_status,
    retry_all_queue,
    retry_single_item
)

urlpatterns = [
    path('hmsmi/create/', create_hmsmi, name='create_hmsmi'),
    path('post-test-results/<path:bill_number>/', post_test_results, name='post-test-results'),
    path('manual-entry/', manual_entry_page, name='manual_entry_page'),
    path('manual-entry/send/', send_manual_result, name='send_manual_result'),
    path('manual-entry/search/', search_machine_records, name='search_machine_records'),
    path('manual-entry/fetch-test-data/', fetch_test_data, name='fetch_test_data'),
    path('manual-entry/queue-status/', get_queue_status, name='get_queue_status'),
    path('manual-entry/retry-all/', retry_all_queue, name='retry_all_queue'),
    path('manual-entry/retry-single/', retry_single_item, name='retry_single_item'),
]
