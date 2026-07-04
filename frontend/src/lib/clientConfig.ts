import { client } from "@/app/openapi-client/client.gen";

const configureClient = () => {
  const baseURL = process.env.NEXT_PUBLIC_API_URL;
  client.setConfig({ baseUrl: baseURL });
};

configureClient();
