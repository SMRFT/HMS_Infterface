from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .serializers import HMSMISerializer

@api_view(['POST'])
def create_hmsmi(request):
    try:
        serializer = HMSMISerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'data': serializer.data,
                'message': 'HMSMI data created successfully.'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'errors': serializer.errors,
                'message': 'Validation failed.'
            }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'errors': str(e),
            'message': 'An unexpected error occurred.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import TestResult
from .serializers import TestResultSerializer


@api_view(['GET'])
def get_test_results(request):
    try:
        results = TestResult.objects.all()
        serializer = TestResultSerializer(results, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'message': 'Test results retrieved successfully.'
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'success': False,
            'errors': str(e),
            'message': 'An unexpected error occurred.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
