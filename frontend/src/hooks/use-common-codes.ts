import { useQuery } from "@tanstack/react-query";
import apiClient from "@/lib/axios";

interface CommonCode {
  group_code: string;
  code: string;
  code_name: string;
  sort_order: number;
}

interface CommonGroupCode {
  group_code: string;
  group_name: string;
  description: string | null;
  codes: CommonCode[];
}

interface ApiResponse<T> {
  success: boolean;
  data: T;
}

export function useCommonCodes() {
  return useQuery({
    queryKey: ["common-codes"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<CommonGroupCode[]>>("/api/v1/codes/groups");
      return data.data;
    },
    staleTime: 60 * 60 * 1000, // 공통코드는 1시간 캐시
  });
}

export function useCodesByGroup(groupCode: string) {
  return useQuery({
    queryKey: ["common-codes", groupCode],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<CommonCode[]>>(`/api/v1/codes/${groupCode}`);
      return data.data;
    },
    enabled: !!groupCode,
    staleTime: 60 * 60 * 1000,
  });
}
