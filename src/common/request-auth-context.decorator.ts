import { createParamDecorator, ExecutionContext } from "@nestjs/common";
import { AuthContext } from "./auth-context.type";

export const RequestAuthContext = createParamDecorator(
  (_: unknown, ctx: ExecutionContext): AuthContext => {
    const request = ctx.switchToHttp().getRequest();
    return request.authContext as AuthContext;
  }
);
