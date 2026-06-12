import { Body, Controller, Get, Param, Post, UseGuards } from "@nestjs/common";
import { ReviewsService } from "./reviews.service";
import { ApiKeyGuard } from "../common/api-key.guard";
import { RequestAuthContext } from "../common/request-auth-context.decorator";
import { AuthContext } from "../common/auth-context.type";

@Controller("reviews")
@UseGuards(ApiKeyGuard)
export class ReviewsController {
  constructor(private readonly reviewsService: ReviewsService) {}

  @Get()
  list(@RequestAuthContext() ctx: AuthContext) {
    return this.reviewsService.list(ctx.tenantId, ctx.appId);
  }

  @Get(":id")
  getOne(@RequestAuthContext() ctx: AuthContext, @Param("id") id: string) {
    return this.reviewsService.getOne(ctx.tenantId, ctx.appId, id);
  }

  @Post(":id/confirm")
  confirm(
    @RequestAuthContext() ctx: AuthContext,
    @Param("id") id: string,
    @Body() body: { payload?: unknown }
  ) {
    return this.reviewsService.confirm({
      tenantId: ctx.tenantId,
      appId: ctx.appId,
      reviewId: id,
      payloadOverride: body.payload,
      actorEmail: ctx.actorEmail,
      actorUserId: ctx.actorUserId
    });
  }

  @Post(":id/reject")
  reject(@RequestAuthContext() ctx: AuthContext, @Param("id") id: string) {
    return this.reviewsService.reject({
      tenantId: ctx.tenantId,
      appId: ctx.appId,
      reviewId: id,
      actorEmail: ctx.actorEmail,
      actorUserId: ctx.actorUserId
    });
  }
}
